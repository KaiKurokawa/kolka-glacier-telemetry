"""
Слой доступа к внешнему телеметрическому API. Stateless-прокси: кэша нет.
fetch_block собирает окно ЦЕЛИКОМ: один запрос с нужным limit, а при 422 /
усечении источника — постраничный добор по offset (шаг 1000). Поэтому модалка
получает год (limit=99999) независимо от того, режет ли источник limit.
"""
import os
import re
from datetime import date, timedelta

import requests

TELEMETRY_BASE_URL = os.getenv("INTERFACE_BASE_URL")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUEST_TIMEOUT = 60
PAGE_SIZE = 1000


def _parse_day(value, fallback):
    s = (value or "").strip()
    return s if _DATE_RE.match(s) else fallback


def _normalize_dates(start_date, end_date):
    today = date.today().isoformat()
    s = _parse_day(start_date, today)
    e = _parse_day(end_date, s)
    if e < s:
        s, e = e, s
    return s, e


def _day_shift(day, delta):
    y, m, d = (int(p) for p in day.split("-"))
    return (date(y, m, d) + timedelta(days=delta)).isoformat()


def _get_page(base_url, s, e, three_h, limit, offset):
    params = {
        "start_date": s, "end_date": e,
        "three_hour_intervals": str(bool(three_h)).lower(),
        "limit": limit, "offset": offset,
    }
    response = requests.get(f"{base_url}/api/v1/telemetry/", params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()          # СНАЧАЛА статус, ПОТОМ разбор тела
    return response.json() or []


def fetch_telemetry(base_url=TELEMETRY_BASE_URL, start_date=None, end_date=None,
                    three_hour_intervals=False, limit=None, offset=0):
    """Одинокий вызов источника. limit=None -> параметр не отправляется."""
    s, e = _normalize_dates(start_date, end_date)
    params = {
        "start_date": s, "end_date": e,
        "three_hour_intervals": str(bool(three_hour_intervals)).lower(),
        "offset": offset,
    }
    if limit is not None:
        params["limit"] = limit
    response = requests.get(f"{base_url}/api/v1/telemetry/", params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _dedup_sort(rows):
    seen, unique = set(), []
    for r in rows:
        key = r.get("id") if r.get("id") is not None else r.get("observation_timestamp")
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    unique.sort(key=lambda r: r["observation_timestamp"])
    return unique


def fetch_block(end_date, days=6, limit=1000, base_url=TELEMETRY_BASE_URL,
                three_hour_intervals=False):
    """
    Полный блок [end_date-days+1 .. end_date] до `limit` записей.
    Стратегия: один запрос с limit; если источник его не принял (422) или
    усёк выдачу — постраничный добор по offset шагом PAGE_SIZE.
    """
    e = _parse_day(end_date, date.today().isoformat())
    s = _day_shift(e, -(max(1, int(days)) - 1))
    limit = max(1, int(limit))

    rows = None
    try:
        rows = _get_page(base_url, s, e, three_hour_intervals, limit, 0)
    except requests.HTTPError as he:
        code = he.response.status_code if he.response is not None else 0
        if code != 422:
            raise
        rows = None                       # источник не принял большой limit -> постранично

    # Признак усечения: просили много, получили ровно PAGE_SIZE или меньше limit.
    need_more = (rows is None) or (limit > PAGE_SIZE and len(rows) >= PAGE_SIZE and len(rows) < limit)
    if need_more:
        collected = list(rows) if rows else []
        offset = len(collected) if rows else 0
        while len(collected) < limit:
            want = min(PAGE_SIZE, limit - len(collected))
            page = _get_page(base_url, s, e, three_hour_intervals, want, offset)
            if not page:
                break
            collected.extend(page)
            if len(page) < want:          # конец данных
                break
            offset += len(page)
        rows = collected

    return {"rows": _dedup_sort(rows or []), "start": s, "end": e}
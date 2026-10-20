from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ..data_store import fetch_telemetry, fetch_block
from ..plotter import build_plots_payload

router = APIRouter(tags=["Страницы"])


@router.get("/")
def index(request: Request):
    return request.app.state.templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/v1/health/")
def health():
    return {"status": "ok", "service": "kolka-proxy"}


@router.get("/api/telemetry")
def api_telemetry(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    three_hour_intervals: bool = Query(False),
    limit: int | None = Query(None, ge=1),
    offset: int = Query(0, ge=0),
):
    now = datetime.now(timezone.utc).isoformat()
    try:
        data = fetch_telemetry(start_date=start_date, end_date=end_date,
                               three_hour_intervals=three_hour_intervals,
                               limit=limit, offset=offset) or []
    except Exception as exc:
        return JSONResponse({"data": [], "latest": None, "plots": {},
                             "last_updated": now, "error": str(exc)})
    latest = max(data, key=lambda d: d["observation_timestamp"]) if data else None
    return JSONResponse({"data": data, "latest": latest,
                         "plots": build_plots_payload(data),
                         "last_updated": now, "error": None})


@router.get("/api/telemetry/block")
def api_telemetry_block(
    end_date: str = Query(...),
    days: int = Query(6, ge=1, le=400),
    limit: int = Query(1000, ge=1, le=200000),
    three_hour_intervals: bool = Query(False),
):
    now = datetime.now(timezone.utc).isoformat()
    try:
        block = fetch_block(end_date=end_date, days=days, limit=limit,
                            three_hour_intervals=three_hour_intervals)
    except Exception as exc:
        return JSONResponse({"data": [], "plots": {}, "window": None,
                             "oldest": None, "newest": None,
                             "last_updated": now, "error": str(exc)})
    rows = block["rows"]
    return JSONResponse({"data": rows, "plots": build_plots_payload(rows),
                         "window": [block["start"], block["end"]],
                         "oldest": rows[0]["observation_timestamp"] if rows else None,
                         "newest": rows[-1]["observation_timestamp"] if rows else None,
                         "last_updated": now, "error": None})
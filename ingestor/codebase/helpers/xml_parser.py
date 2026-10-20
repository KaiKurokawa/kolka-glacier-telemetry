"""
Парсер XML-файлов телеметрии метеостанций.

Принимает на вход содержимое XML-файла, возвращает список нормализованных
словарей — по одному на каждую секцию <report> внутри <message>.

Каждый словарь готов для отправки в API или сохранения в базу данных.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any


# -------------------------------------------------------------------------
# Маппинг кодов переменных на названия полей
# -------------------------------------------------------------------------

VARIABLE_FIELD_NAMES = {
    "WS": "wind_speed",                  # скорость ветра
    "WD": "wind_direction",              # направление ветра
    "TA": "air_temperature",             # температура воздуха
    "RH": "relative_humidity",           # относительная влажность
    "AP": "atmospheric_pressure",        # атмосферное давление
    "LB": "battery_voltage",             # напряжение батареи
    "PI": "precipitation_intensity",     # интенсивность осадков
    "P":  "precipitation",               # осадки
    "HS": "snow_depth",                  # высота снежного покрова
}


# Маппинг высот/уровней измерения на суффиксы полей
HEIGHT_SUFFIXES = {
    "2M":  "at_2m",
    "10M": "at_10m",
    "STN": "at_station",
    "MSL": "at_mean_sea_level",
    "S":   "at_surface",
}


# Маппинг способов обработки (PROC) на суффиксы полей
PROC_SUFFIXES = {
    "INS":   "instantaneous",
    "AVE":   "average",
    "MAX":   "maximum",
    "MIN":   "minimum",
    "SUM":   "sum",
    "ACC":   "accumulated",
    "DELTA": "delta",
    "ERR":   "error",
}


# Значения, означающие отсутствие данных в XML
MISSING_DATA_MARKERS = {"//", "/", "*", ""}


# -------------------------------------------------------------------------
# Вспомогательные функции
# -------------------------------------------------------------------------

def _parse_number(raw_value: str | None) -> float | None:
    """
    Преобразует строковое значение в число.

    Возвращает None для пропусков данных ("//", "/", "*", пустая строка)
    и для значений, которые не удаётся преобразовать в число.
    """

    if raw_value is None:
        return None

    normalized = raw_value.strip()

    if normalized in MISSING_DATA_MARKERS:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_datetime(time_string: str | None) -> datetime | None:
    """
    Парсит строку времени из атрибута TIME элемента <report>.

    Поддерживает форматы с часовым поясом и без него.
    """

    if not time_string:
        return None

    time_string = time_string.strip()

    # Пробуем несколько распространённых форматов
    for format_template in (
        "%Y-%m-%dT%H:%M:%S%z",     # 2026-09-29T15:00:00+03:00
        "%Y-%m-%dT%H:%M:%SZ",      # 2026-09-29T15:00:00Z
        "%Y-%m-%dT%H:%M:%S",       # 2026-09-29T15:00:00 (без таймзоны)
        "%d-%m-%YT%H:%M:%S%z",     # 29-09-2026T15:00:00+03:00 (по спецификации)
        "%d-%m-%YT%H:%M:%S",       # 29-09-2026T15:00:00
    ):
        try:
            return datetime.strptime(time_string, format_template)
        except ValueError:
            continue

    return None


def _build_field_name(
    variable_code: str,
    height_code: str | None,
    proc_code: str | None,
) -> str | None:
    """
    Собирает имя поля для базы данных из трёх частей:
    VARIABLE_height_PROC.

    Пример:
        ("WS", "10M", "AVE") -> "wind_speed_average_at_10m"
        ("AP", "MSL", "AVE") -> "atmospheric_pressure_average_at_mean_sea_level"
        ("P",  None,  "ACC") -> "precipitation_accumulated"

    Если переменная неизвестна, возвращает None (поле будет проигнорировано).
    """

    variable_name = VARIABLE_FIELD_NAMES.get(variable_code)
    if variable_name is None:
        return None

    proc_name = PROC_SUFFIXES.get(proc_code) if proc_code else None
    height_name = HEIGHT_SUFFIXES.get(height_code) if height_code else None

    # Собираем части в порядке: variable + proc + height
    parts = [variable_name]

    # Особый случай для осадков: SUM и ACC имеют отдельные названия
    if variable_code == "P" and proc_code == "ACC":
        return "precipitation_accumulated"
    if variable_code == "P" and proc_code == "SUM":
        return "precipitation_sum"

    if proc_name:
        parts.append(proc_name)

    if height_name:
        parts.append(height_name)

    return "_".join(parts)


# -------------------------------------------------------------------------
# Извлечение данных из одного элемента <parameter>
# -------------------------------------------------------------------------

def _extract_parameter_values(parameter_element: ET.Element) -> list[dict[str, Any]]:
    """
    Извлекает все значения из элемента <parameter>.

    Возвращает список словарей вида:
        {"proc": "AVE", "value": 13.4, "height": "2M", "status": 0}

    Обрабатывает два случая:
    1. Значения во вложенных <value PROC="...">...</value>
    2. Одно значение прямо в тексте <parameter VAR="...">65</parameter>
    """

    # Атрибуты самого параметра (могут служить дефолтом для дочерних value)
    default_proc = parameter_element.get("PROC")
    height = parameter_element.get("Z")
    status_raw = parameter_element.get("STATUS")
    status = int(status_raw) if status_raw and status_raw.lstrip("-").isdigit() else None

    result: list[dict[str, Any]] = []

    # Ищем дочерние <value>
    child_values = parameter_element.findall("value")

    if child_values:
        # Случай 1: значения во вложенных тегах <value>
        for value_element in child_values:
            proc = value_element.get("PROC") or default_proc
            value = _parse_number(value_element.text)

            result.append({
                "proc": proc,
                "value": value,
                "height": height,
                "status": status,
            })
    else:
        # Случай 2: значение прямо в тексте <parameter>
        value = _parse_number(parameter_element.text)

        result.append({
            "proc": default_proc,
            "value": value,
            "height": height,
            "status": status,
        })

    return result


# -------------------------------------------------------------------------
# Извлечение информации о станции
# -------------------------------------------------------------------------

def _extract_station_info(report_element: ET.Element) -> dict[str, Any]:
    """
    Извлекает данные станции из тега <station> внутри <report>.

    Возвращает словарь:
        {
            "station_identifier": "77777",
            "latitude": 55.8623,
            "longitude": 37.4857,
            "altitude": 0,
        }
    """

    station_element = report_element.find("station")

    if station_element is None:
        return {
            "station_identifier": None,
            "latitude": None,
            "longitude": None,
            "altitude": None,
        }

    return {
        "station_identifier": station_element.get("ID"),
        "latitude": _parse_number(station_element.get("LAT")),
        "longitude": _parse_number(station_element.get("LON")),
        "altitude": _parse_number(station_element.get("Z")),
    }


# -------------------------------------------------------------------------
# Главная функция парсинга
# -------------------------------------------------------------------------

def parse_telemetry_xml(xml_content: str | bytes) -> list[dict[str, Any]]:
    """
    Парсит XML-файл телеметрии и возвращает список нормализованных записей.

    Аргументы:
        xml_content: содержимое XML-файла (строка или байты)

    Возвращает:
        Список словарей, по одному на каждую секцию <report>.
        Каждый словарь содержит поля с понятными именами, готовые для
        отправки в API или сохранения в базу данных.

    Пример результата для одного <report>:
        {
            "observation_timestamp": datetime(2026, 9, 29, 15, 0),
            "station_identifier": "77777",
            "latitude": 55.8623,
            "longitude": 37.4857,
            "altitude": 0,
            "wind_speed_average_at_10m": 0.3,
            "wind_speed_maximum_at_10m": 0.5,
            "wind_direction_average_at_10m": 147.0,
            "air_temperature_average_at_2m": 13.4,
            "air_temperature_maximum_at_2m": 13.4,
            "air_temperature_minimum_at_2m": 13.3,
            "relative_humidity_average_at_2m": 65.0,
            "atmospheric_pressure_average_at_station": 1011.6,
            "atmospheric_pressure_average_at_mean_sea_level": 1033.4,
            "battery_instantaneous_voltage": 45.2,
            "precipitation_intensity_average_at_2m": 0.0,
            "precipitation_sum": None,
            "precipitation_accumulated": 0.0,
            "snow_depth_instantaneous": 90.8,
            "snow_depth_average": 92.2,
            "snow_depth_maximum": 96.9,
            "snow_depth_minimum": 88.9,
        }
    """

    root = ET.fromstring(xml_content)
    records: list[dict[str, Any]] = []

    for report_element in root.findall("report"):
        # Базовая информация о наблюдении
        record: dict[str, Any] = {
            "observation_timestamp": _parse_datetime(report_element.get("TIME")),
        }

        # Информация о станции
        record.update(_extract_station_info(report_element))

        # Обработка всех параметров
        for parameter_element in report_element.findall("parameter"):
            variable_code = parameter_element.get("VAR")
            if not variable_code:
                continue

            for value_info in _extract_parameter_values(parameter_element):
                field_name = _build_field_name(
                    variable_code=variable_code,
                    height_code=value_info["height"],
                    proc_code=value_info["proc"],
                )

                if field_name is None:
                    # Неизвестная переменная — пропускаем
                    continue

                # Если поле уже есть (мало ли), перезаписываем последним значением
                record[field_name] = value_info["value"]

        records.append(record)

    return records

"""
HTTP-клиент для взаимодействия с программным интерфейсом телеметрии.
"""

import logging
from datetime import date, datetime
from typing import Any

import httpx

from .. import configuration


logger = logging.getLogger(__name__)


def _serialize_value(value: Any) -> Any:
    """
    Рекурсивно подготавливает значения для JSON-сериализации.
    Объекты datetime и date конвертируются в ISO-строки.
    """

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_serialize_value(item) for item in value]

    return value


def check_health() -> bool:
    """
    Проверяет доступность API через healthcheck эндпоинт.

    Возвращает True, если API отвечает status=ready.
    """

    health_url = f"{configuration.API_BASE_URL}{configuration.API_HEALTH_PATH}"

    try:
        response = httpx.get(health_url, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            return data.get("status") == "ready"

        logger.warning(f"API healthcheck вернул {response.status_code}")
        return False

    except httpx.RequestError as error:
        logger.error(f"API недоступен: {error}")
        return False


def upload_records(records: list[dict[str, Any]]) -> dict[str, int]:
    """
    Отправляет пакет записей в API.

    Возвращает словарь со статистикой:
        {"inserted": N, "skipped": M, "total": K, "success": bool}

    При сетевой ошибке или ошибке API:
        {"inserted": 0, "skipped": 0, "total": K, "success": False}
    """

    upload_url = f"{configuration.API_BASE_URL}{configuration.API_TELEMETRY_PATH}"
    serialized_records = [_serialize_value(record) for record in records]
    payload = {"records": serialized_records}

    try:
        response = httpx.post(
            upload_url,
            json=payload,
            timeout=configuration.API_TIMEOUT_SECONDS,
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "inserted": data.get("inserted", 0),
                "skipped": data.get("skipped", 0),
                "total": data.get("total", 0),
                "success": True,
            }

        logger.error(f"API вернул ошибку {response.status_code}: {response.text[:500]}")
        return {
            "inserted": 0,
            "skipped": 0,
            "total": len(records),
            "success": False,
        }

    except httpx.RequestError as error:
        logger.error(f"Сетевая ошибка при отправке в API: {error}")
        return {
            "inserted": 0,
            "skipped": 0,
            "total": len(records),
            "success": False,
        }


def upload_photos_to_api(
    photos: list[dict[str, Any]],
    station_id: str,
    caption: str | None = None,
) -> dict[str, Any] | None:
    """
    Отправляет пакет фотографий в API через multipart/form-data.

    Аргументы:
        photos: список словарей с полями:
            - filename: имя файла
            - file_bytes: содержимое файла
            - observation_timestamp: время съёмки (ISO-строка)
        station_id: идентификатор станции
        caption: подпись к фотографиям (опционально)

    Возвращает ответ API или None при ошибке.
    """
    upload_url = f"{configuration.API_BASE_URL}{configuration.API_PHOTOS_PATH}"

    if not photos:
        return None

    try:
        # Формируем файлы для multipart
        files = []
        for photo in photos:
            files.append(
                ("files", (photo["filename"], photo["file_bytes"], "image/jpeg"))
            )

        # Формируем дополнительные поля
        data = {
            "station_id": station_id,
        }

        if caption:
            data["caption"] = caption

        response = httpx.post(
            upload_url,
            data=data,
            files=files,
            timeout=configuration.API_TIMEOUT_SECONDS,
        )

        if response.status_code == 200:
            return response.json()

        logger.error(
            f"API вернул ошибку при загрузке фотографий: "
            f"{response.status_code} - {response.text[:300]}"
        )
        return None

    except httpx.RequestError as error:
        logger.error(f"Сетевая ошибка при загрузке фотографий: {error}")
        return None

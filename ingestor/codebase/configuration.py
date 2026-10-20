"""
Конфигурация сервиса ingestor.
Все параметры читаются из переменных окружения при запуске.
"""

import os
import sys


def _require_env(name: str) -> str:
    """Читает обязательную переменную окружения. Прерывает запуск при отсутствии."""

    value = os.getenv(name)

    if not value:
        print(f"❌ Критическая ошибка: переменная окружения {name} не задана или пуста.", flush=True)
        sys.exit(1)

    return value


# FTP-сервер
FTP_HOST_ADDRESS = _require_env("INGESTOR_FTP_HOST_ADDRESS")
FTP_HOST_USER = _require_env("INGESTOR_FTP_HOST_USER")
FTP_HOST_PASSWORD = _require_env("INGESTOR_FTP_HOST_PASSWORD")
FTP_TELEMETRY_PATH = _require_env("INGESTOR_FTP_HOST_XML_PATH")
FTP_JPG_PATH = _require_env("INGESTOR_FTP_HOST_JPG_PATH")

# Идентификатор станции по умолчанию (используется для фотографий)
DEFAULT_STATION_ID = os.getenv("DEFAULT_STATION_ID", "37326")

# Программный интерфейс
API_BASE_URL = _require_env("INTERFACE_BASE_URL")
API_TELEMETRY_PATH = "/api/v1/telemetry/upload"
API_PHOTOS_PATH = "/api/v1/photos/upload"
API_HEALTH_PATH = "/api/v1/health/"

# Таймауты
FTP_TIMEOUT_SECONDS = 60
API_TIMEOUT_SECONDS = 30.0

# Обработка архивов
DELETE_PROCESSED_ARCHIVES = os.getenv("DELETE_PROCESSED_ARCHIVES", "true").lower() in (
    "true",
    "1",
    "yes",
)

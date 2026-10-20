"""
Конфигурация сервиса interface.
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


# MinIO / Object Storage
MINIO_ENDPOINT = os.getenv("OBJECT_STORAGE_BASE_URL")
MINIO_ACCESS_KEY = _require_env("OBJECT_STORAGE_DEFAULT_USER")
MINIO_SECRET_KEY = _require_env("OBJECT_STORAGE_DEFAULT_PASSWORD")
MINIO_BUCKET_NAME = os.getenv("OBJECT_STORAGE_BUCKET")
MINIO_SECURE = os.getenv("OBJECT_STORAGE_USE_SSL", "false").lower() in ("true", "1", "yes")

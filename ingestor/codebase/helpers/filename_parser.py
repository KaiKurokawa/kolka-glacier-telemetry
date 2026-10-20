"""
Парсер имён файлов фотографий.

Формат имени JPG: {camera_id}_{YYYY-MM-DD-HH-MM-SS}.JPG
Пример: 2_2026-08-14-16-42-16.JPG
"""

import re
from datetime import datetime
from typing import NamedTuple


class ParsedFilename(NamedTuple):
    """Результат парсинга имени файла."""

    camera_id: int
    observation_timestamp: datetime
    original_filename: str


# Регулярное выражение для парсинга имени файла
# Формат: {camera_id}_{YYYY-MM-DD-HH-MM-SS}.{ext}
_JPG_FILENAME_PATTERN = re.compile(
    r"^(\d+)_(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})\.(jpe?g|JPG|JPEG)$",
    re.IGNORECASE,
)


def parse_jpg_filename(filename: str) -> ParsedFilename | None:
    """
    Парсит имя JPG-файла и извлекает camera_id и observation_timestamp.

    Возвращает ParsedFilename при успехе, None если формат не распознан.
    """

    match = _JPG_FILENAME_PATTERN.match(filename)

    if not match:
        return None

    camera_id = int(match.group(1))
    year = int(match.group(2))
    month = int(match.group(3))
    day = int(match.group(4))
    hour = int(match.group(5))
    minute = int(match.group(6))
    second = int(match.group(7))

    try:
        observation_timestamp = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None

    return ParsedFilename(
        camera_id=camera_id,
        observation_timestamp=observation_timestamp,
        original_filename=filename,
    )

"""
Модуль распаковки архивов формата bzip2.
"""

import bz2
import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def decompress_bzip_archive(archive_path: Path, destination_path: Path) -> None:
    """
    Распаковывает bzip2-архив в целевой XML-файл.

    Аргументы:
        archive_path: путь к .bz2 файлу
        destination_path: путь, куда будет записан распакованный XML
    """

    try:
        compressed_data = archive_path.read_bytes()
        decompressed_data = bz2.decompress(compressed_data)
        destination_path.write_bytes(decompressed_data)

    except Exception as error:
        raise IOError(f"Повреждён архив или ошибка распаковки: {error}") from error

"""
Обёртка над ftplib для работы с FTP-сервером метеостанции.

Предоставляет высокоуровневые операции: список файлов, скачивание, загрузка,
удаление. Все методы работают в контексте текущей директории FTP-сервера.
"""

import ftplib
import logging
from pathlib import Path

from .. import configuration


logger = logging.getLogger(__name__)


class FTPClient:
    """Клиент для работы с FTP-сервером."""

    def __init__(self):
        self._connection: ftplib.FTP | None = None

    def connect(self) -> None:
        """Устанавливает соединение с FTP-сервером в пассивном режиме."""

        logger.info(f"🔌 Подключение к {configuration.FTP_HOST_ADDRESS}...")

        self._connection = ftplib.FTP(
            configuration.FTP_HOST_ADDRESS,
            configuration.FTP_HOST_USER,
            configuration.FTP_HOST_PASSWORD,
            timeout=configuration.FTP_TIMEOUT_SECONDS,
        )

        # Пассивный режим обязателен для работы через NAT и внутри Docker
        self._connection.set_pasv(True)

        logger.info("✅ Соединение с FTP установлено.")

    def close(self) -> None:
        """Корректно закрывает соединение."""

        if self._connection is not None:
            try:
                self._connection.quit()
            except ftplib.all_errors:
                pass

            self._connection = None

    def change_directory(self, path: str) -> None:
        """Переходит в указанную директорию на сервере."""

        self._connection.cwd(path)
        logger.info(f"📂 Текущая директория: {path}")

    def list_files(self) -> list[str]:
        """Возвращает список имён файлов в текущей директории."""

        return self._connection.nlst()

    def download_file(self, remote_filename: str, local_path: Path) -> None:
        """Скачивает файл с сервера в локальный путь."""

        with open(local_path, "wb") as file_stream:
            self._connection.retrbinary(f"RETR {remote_filename}", file_stream.write)

    def upload_file(self, local_path: Path, remote_filename: str) -> None:
        """Загружает локальный файл на сервер."""

        with open(local_path, "rb") as file_stream:
            self._connection.storbinary(f"STOR {remote_filename}", file_stream)

    def delete_file(self, remote_filename: str) -> None:
        """Удаляет файл на сервере."""

        self._connection.delete(remote_filename)

    def rename_file(self, old_name: str, new_name: str) -> None:
        """Переименовывает или перемещает файл на сервере."""

        self._connection.rename(old_name, new_name)

    def ensure_directory_exists(self, base_path: str, subdirectory: str) -> None:
        """Создаёт поддиректорию, если она не существует."""

        original_directory = self._connection.pwd()

        try:
            self._connection.cwd(base_path)
            self._connection.cwd(subdirectory)
            logger.info(f"📂 Каталог '{subdirectory}' уже существует.")

        except ftplib.error_perm:
            logger.info(f"📂 Каталог '{subdirectory}' не найден. Создаём...")
            self._connection.cwd(base_path)
            self._connection.mkd(subdirectory)

        finally:
            self._connection.cwd(original_directory)

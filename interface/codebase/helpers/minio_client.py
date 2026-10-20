"""
Клиент для работы с объектным хранилищем MinIO.
Реализует загрузку фотографий с детерминированным именованием на основе хэша содержимого.
"""

import hashlib
from datetime import datetime
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from .. import configuration


class MinIOClient:
    """Асинхронно-совместимый клиент MinIO."""

    def __init__(self):
        self._client = Minio(
            endpoint=configuration.MINIO_ENDPOINT,
            access_key=configuration.MINIO_ACCESS_KEY,
            secret_key=configuration.MINIO_SECRET_KEY,
            secure=configuration.MINIO_SECURE,
        )
        self._bucket = configuration.MINIO_BUCKET_NAME
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Создаёт бакет, если он не существует."""
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)

        except S3Error as error:
            raise RuntimeError(f"Ошибка инициализации MinIO бакета: {error}") from error

    @staticmethod
    def _compute_hash(file_bytes: bytes) -> str:
        """Вычисляет SHA-256 хэш содержимого файла."""
        return hashlib.sha256(file_bytes).hexdigest()

    def upload_photo(
        self,
        station_id: str,
        camera_id: int,
        observation_timestamp: datetime,
        original_filename: str,
        file_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> dict:
        """
        Загружает фотографию в MinIO по детерминированному пути.

        Путь: {station_id}/camera_{camera_id}/{YYYY}/{MM}/{DD}/{hash}_{original_filename}
        """

        date_path = observation_timestamp.strftime("%Y/%m/%d")
        content_hash = self._compute_hash(file_bytes)
        
        safe_name = original_filename.replace("/", "_").replace("\\", "_")
        object_key = f"{station_id}/camera_{camera_id}/{date_path}/{content_hash[:16]}_{safe_name}"

        data_stream = BytesIO(file_bytes)
        file_size = len(file_bytes)

        try:
            self._client.put_object(
                bucket_name=self._bucket,
                object_name=object_key,
                data=data_stream,
                length=file_size,
                content_type=content_type,
                metadata={
                    "station-id": station_id,
                    "camera-id": str(camera_id),
                    "observation-time": observation_timestamp.isoformat(),
                    "original-filename": safe_name,
                    "content-hash": content_hash,
                },
            )
        except S3Error as error:
            raise RuntimeError(f"Ошибка загрузки в MinIO: {error}") from error

        return {
            "object_key": object_key,
            "content_hash": content_hash,
            "size_bytes": file_size,
            "bucket": self._bucket,
        }

    def download_object(self, object_key: str) -> bytes:
        """Скачивает объект из MinIO и возвращает его содержимое как байты."""

        try:
            response = self._client.get_object(
                bucket_name=self._bucket,
                object_name=object_key,
            )

            try:
                return response.read()

            finally:
                response.close()
                response.release_conn()

        except S3Error as error:
            raise RuntimeError(f"Ошибка чтения объекта из MinIO: {error}") from error

    def delete_object(self, object_key: str) -> None:
        """Удаляет объект из MinIO."""

        try:
            self._client.remove_object(
                bucket_name=self._bucket,
                object_name=object_key,
            )
        except S3Error as error:
            raise RuntimeError(f"Ошибка удаления объекта из MinIO: {error}") from error

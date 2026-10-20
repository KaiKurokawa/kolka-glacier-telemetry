"""
Схемы Pydantic для работы с фотографиями.
"""

from datetime import datetime, date

from pydantic import BaseModel, ConfigDict, Field


class PhotoUploadRequest(BaseModel):
    """Форма пакетной загрузки изображений (multipart/form-data)."""

    observation_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Дата съёмки (YYYY-MM-DD), общая для всех файлов пакета. Если не указана — используется дата из имени файла.",
    )

    caption: str | None = Field(
        default=None,
        max_length=200,
        description="Подпись к изображениям пакета (необязательно)",
    )


class PhotoRecordResponse(BaseModel):
    """Метаданные одного изображения станции."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    observation_date: date
    camera_id: int = Field(
        description="Номер камеры, извлечённый из имени файла (первая цифра до подчёркивания)",
    )
    caption: str | None = None
    file_name: str
    content_type: str
    url: str
    size_bytes: int
    created_at: datetime


class PhotoUploadResult(BaseModel):
    """Результат пакетной загрузки изображений."""

    inserted: int = Field(description="Количество добавленных изображений")
    skipped: int = Field(description="Количество пропущенных дубликатов")
    total: int = Field(description="Общее количество файлов в пакете")
    photos: list[PhotoRecordResponse] = Field(description="Метаданные добавленных изображений")


class PhotoDeleteResult(BaseModel):
    """Результат удаления изображения."""

    id: int
    deleted: bool = Field(description="Признак успешного удаления")

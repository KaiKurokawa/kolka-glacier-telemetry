"""
Маршруты API для работы с фотографиями метеостанции.
"""

from datetime import datetime, date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..database.models import PhotoRecord
from ..database.session import async_session
from ..helpers.minio_client import MinIOClient
from ..helpers.filename_parser import parse_photo_filename
from ..schemas.photos import (
    PhotoRecordResponse,
    PhotoUploadResult,
    PhotoDeleteResult,
)


router = APIRouter(prefix="/api/v1/photos", tags=["Фотографии"])

_minio = MinIOClient()


async def get_session():
    async with async_session() as session:
        yield session


def _build_photo_response(record: PhotoRecord) -> dict:
    """Формирует ответ для одной фотографии."""
    return {
        "id": record.id,
        "observation_date": record.observation_date,
        "camera_id": record.camera_id,
        "caption": record.caption,
        "file_name": record.file_name,
        "content_type": record.content_type or "image/jpeg",
        "url": f"/api/v1/photos/{record.id}/image",
        "size_bytes": record.size_bytes or 0,
        "created_at": record.created_at,
    }


@router.post(
    "/upload",
    response_model=PhotoUploadResult,
    summary="Загрузить пакет изображений",
)
async def upload_photos(
    files: Annotated[
        list[UploadFile],
        File(description="Файлы изображений, от 1 до 50 за один запрос"),
    ],
    observation_date: str | None = Form(
        None,
        description="Дата съёмки (YYYY-MM-DD), общая для всех файлов пакета",
    ),
    caption: str | None = Form(
        None,
        description="Подпись к изображениям пакета (необязательно)",
    ),
    station_id: str = Form(
        "37326",
        description="Идентификатор станции",
    ),
    db: AsyncSession = Depends(get_session),
):
    """
    Принимает от 1 до 50 файлов изображений (JPEG, PNG, WebP) вместе с датой съёмки.

    Дубликаты (та же дата съёмки и то же имя файла) пропускаются.
    Файлы сохраняются в хранилище, метаданные — в базу данных.
    """

    if len(files) > 50:
        raise HTTPException(
            status_code=400,
            detail=f"Слишком много файлов: {len(files)}. Максимум 50.",
        )

    # Парсим observation_date если передана
    obs_date_obj = None
    if observation_date:
        try:
            obs_date_obj = datetime.strptime(observation_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Некорректный формат даты: {observation_date}. Ожидается YYYY-MM-DD",
            )

    inserted_photos = []
    inserted_count = 0
    skipped_count = 0

    for file in files:
        file_bytes = await file.read()

        if not file_bytes:
            skipped_count += 1
            continue

        # Парсим имя файла
        parsed = parse_photo_filename(file.filename or "", station_id)

        if parsed is None:
            skipped_count += 1
            continue

        # Определяем дату съёмки
        observation_date_value = obs_date_obj or parsed.observation_timestamp.date()

        # Определяем content-type
        content_type = file.content_type or "image/jpeg"

        # Загружаем в MinIO
        try:
            result = await run_in_threadpool(
                _minio.upload_photo,
                station_id=station_id,
                camera_id=parsed.camera_id,
                observation_timestamp=parsed.observation_timestamp,
                original_filename=parsed.original_filename,
                file_bytes=file_bytes,
                content_type=content_type,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=f"Хранилище недоступно: {e}")

        # Сохраняем метаданные в БД
        photo_record = PhotoRecord(
            observation_timestamp=parsed.observation_timestamp,
            observation_date=observation_date_value,
            camera_id=parsed.camera_id,
            station_identifier=station_id,
            caption=caption,
            file_name=parsed.original_filename,
            object_key=result["object_key"],
            content_hash=result["content_hash"],
            size_bytes=result["size_bytes"],
            content_type=content_type,
        )

        db.add(photo_record)

        try:
            await db.commit()
            await db.refresh(photo_record)
            inserted_photos.append(_build_photo_response(photo_record))
            inserted_count += 1
        except IntegrityError:
            await db.rollback()
            skipped_count += 1

    return PhotoUploadResult(
        inserted=inserted_count,
        skipped=skipped_count,
        total=len(files),
        photos=inserted_photos,
    )


@router.get(
    "/",
    response_model=list[PhotoRecordResponse],
    summary="Получить список изображений за диапазон дат",
)
async def list_photos(
    start_date: str | None = Query(
        None,
        description="Начальная дата съёмки в формате YYYY-MM-DD.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    end_date: str | None = Query(
        None,
        description="Конечная дата съёмки в формате YYYY-MM-DD.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    camera_id: int | None = Query(
        None,
        description="Фильтр по номеру камеры",
    ),
    limit: int = Query(100, ge=1, le=1000, description="Лимит записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
    db: AsyncSession = Depends(get_session),
):
    """
    Возвращает метаданные изображений за указанный диапазон дат съёмки.

    Сортировка: по дате съёмки по убыванию (свежие первыми), затем по времени загрузки по убыванию.
    Если даты не указаны — возвращаются все имеющиеся изображения.
    """

    query = select(PhotoRecord)

    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.where(PhotoRecord.observation_date >= start_date_obj)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный формат start_date")

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.where(PhotoRecord.observation_date <= end_date_obj)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный формат end_date")

    if camera_id is not None:
        query = query.where(PhotoRecord.camera_id == camera_id)

    query = (
        query
        .order_by(desc(PhotoRecord.observation_date), desc(PhotoRecord.created_at))
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    records = result.scalars().all()

    return [_build_photo_response(record) for record in records]


@router.get(
    "/latest",
    response_model=list[PhotoRecordResponse],
    summary="Получить последние изображения",
)
async def latest_photos(
    limit: int = Query(
        4,
        ge=1,
        le=50,
        description="Сколько последних изображений вернуть (дашборд использует 4)",
    ),
    db: AsyncSession = Depends(get_session),
):
    """
    Возвращает последние N изображений: сортировка по дате съёмки по убыванию,
    затем по времени загрузки по убыванию.

    Дашборд запрашивает limit=4 для четырёх фоторамок левой колонки.
    Если изображений нет — возвращается пустой массив.
    """

    query = (
        select(PhotoRecord)
        .order_by(desc(PhotoRecord.observation_date), desc(PhotoRecord.created_at))
        .limit(limit)
    )

    result = await db.execute(query)
    records = result.scalars().all()

    return [_build_photo_response(record) for record in records]


@router.get(
    "/latest_per_camera",
    response_model=list[PhotoRecordResponse],
    summary="Получить последние фото по каждой камере",
)
async def latest_photos_per_camera(
    db: AsyncSession = Depends(get_session),
):
    """
    Возвращает по одному последнему фото для каждой камеры.

    Если за сегодня фото нет, возвращает последние доступные фото по каждой камере.
    Используется для слотов камер на дашборде.
    """

    # DISTINCT ON работает только в PostgreSQL
    # Для каждой камеры берём самую свежую запись
    query = (
        select(PhotoRecord)
        .distinct(PhotoRecord.camera_id)
        .order_by(PhotoRecord.camera_id, desc(PhotoRecord.observation_timestamp))
    )

    result = await db.execute(query)
    records = result.scalars().all()

    return [_build_photo_response(record) for record in records]


@router.get(
    "/{photo_id}",
    response_model=PhotoRecordResponse,
    summary="Получить метаданные изображения по ID",
)
async def get_photo(
    photo_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Возвращает метаданные одного изображения по его уникальному идентификатору."""

    result = await db.execute(
        select(PhotoRecord).where(PhotoRecord.id == photo_id)
    )

    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=404, detail="Изображение не найдено")

    return _build_photo_response(record)


@router.get(
    "/{photo_id}/image",
    summary="Скачать изображение",
)
async def get_photo_image(
    photo_id: int,
    db: AsyncSession = Depends(get_session),
):
    """
    Проксирует изображение из MinIO.

    Используется фронтендом для отображения фотографий через <img src="...">.
    """

    result = await db.execute(
        select(PhotoRecord).where(PhotoRecord.id == photo_id)
    )

    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=404, detail="Изображение не найдено")

    try:
        file_bytes = await run_in_threadpool(
            _minio.download_object,
            record.object_key,
        )
    except RuntimeError as e:
        if "NoSuchKey" in str(e):
            raise HTTPException(status_code=404, detail="Файл не найден в хранилище")
        raise HTTPException(status_code=503, detail=f"Не удалось получить файл: {e}")

    return Response(
        content=file_bytes,
        media_type=record.content_type or "image/jpeg",
    )


@router.delete(
    "/{photo_id}",
    response_model=PhotoDeleteResult,
    summary="Удалить изображение по ID",
)
async def delete_photo(
    photo_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Удаляет файл из хранилища и метаданные из базы данных."""

    result = await db.execute(
        select(PhotoRecord).where(PhotoRecord.id == photo_id)
    )

    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=404, detail="Изображение не найдено")

    # Удаляем из MinIO
    try:
        await run_in_threadpool(_minio.delete_object, record.object_key)
    except RuntimeError:
        # Если файл уже удалён из MinIO, продолжаем удаление из БД
        pass

    # Удаляем из БД
    await db.delete(record)
    await db.commit()

    return PhotoDeleteResult(id=photo_id, deleted=True)

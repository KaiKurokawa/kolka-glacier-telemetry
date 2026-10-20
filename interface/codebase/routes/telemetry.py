"""
Маршруты API для работы с метеоданными.
"""

from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, extract
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.session import async_session
from ..database.models import TelemetryRecord
from ..schemas.telemetry import (
    TelemetryBatchUploadResult,
    TelemetryRecordBatchUpload,
    TelemetryRecordCreate,
    TelemetryRecordResponse,
)


router = APIRouter(prefix="/api/v1/telemetry", tags=["Телеметрия"])


# --------------------------------------------------------------------------
# Список всех полей, которые принимает модель.
# Используется для фильтрации входящих данных от парсера:
# если парсер в будущем начнёт отдавать новые поля, которые ещё не добавлены
# в модель, они будут просто отброшены без падения API.
# --------------------------------------------------------------------------

_KNOWN_FIELDS = set(TelemetryRecordCreate.model_fields.keys())


async def get_session():
    """Генератор сессий базы данных для Dependency Injection."""

    async with async_session() as session:
        yield session


@router.post(
    "/upload",
    response_model=TelemetryBatchUploadResult,
    summary="Загрузить пакет метеоданных",
)
async def upload_telemetry_records(
    batch: TelemetryRecordBatchUpload,
    db: AsyncSession = Depends(get_session),
):
    """
    Загружает пакет метеорологических записей в базу данных.

    Дубликаты (записи с одинаковыми station_identifier и observation_timestamp)
    пропускаются. Неизвестные поля отбрасываются.
    """

    inserted_count = 0
    skipped_count = 0

    for record in batch.records:
        # Pydantic уже провалидировал структуру, берём словарь
        payload = record.model_dump()

        # Фильтруем на случай если парсер пришлёт неизвестные поля
        payload = {k: v for k, v in payload.items() if k in _KNOWN_FIELDS}

        # Ищем существующую запись по уникальной паре
        existing = await db.execute(
            select(TelemetryRecord).where(
                TelemetryRecord.station_identifier == payload.get("station_identifier"),
                TelemetryRecord.observation_timestamp == payload.get("observation_timestamp"),
            )
        )

        if existing.scalar_one_or_none() is not None:
            skipped_count += 1
            continue

        db.add(TelemetryRecord(**payload))
        inserted_count += 1

    try:
        await db.commit()
    except IntegrityError:
        # На случай гонки: две параллельные загрузки вставили одну и ту же запись
        await db.rollback()
        # Возвращаем то, что успели вставить до ошибки
        pass

    return TelemetryBatchUploadResult(
        inserted=inserted_count,
        skipped=skipped_count,
        total=len(batch.records),
    )


@router.get(
    "/",
    response_model=list[TelemetryRecordResponse],
    summary="Получить список метеозаписей",
)
async def get_telemetry_records(
    start_date: str | None = Query(
        None,
        description="Начальная дата в формате YYYY-MM-DD. По умолчанию сегодня.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    end_date: str | None = Query(
        None,
        description="Конечная дата в формате YYYY-MM-DD. По умолчанию сегодня.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    three_hour_intervals: bool = Query(
        False,
        description="Фильтр: только записи каждые 3 часа (00, 03, 06, 09, 12, 15, 18, 21)",
    ),
    limit: int = Query(1000, ge=1, le=50000, description="Лимит записей"),  # Увеличено с 1000 до 50000
    offset: int = Query(0, ge=0, description="Смещение"),
    db: AsyncSession = Depends(get_session),
):
    """
    Возвращает список метеорологических записей.

    Поддерживает фильтрацию по диапазону дат и трёхчасовым интервалам.
    Если даты не указаны, возвращает данные за текущие сутки.
    """

    today = date.today()

    if start_date is None:
        start_date_obj = today
    else:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Некорректный формат начальной даты. Ожидается YYYY-MM-DD",
            )

    if end_date is None:
        end_date_obj = today
    else:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Некорректный формат конечной даты. Ожидается YYYY-MM-DD",
            )

    if start_date_obj > end_date_obj:
        raise HTTPException(
            status_code=400,
            detail="Начальная дата не может быть больше конечной",
        )

    query = select(TelemetryRecord).where(
        func.date(TelemetryRecord.observation_timestamp) >= start_date_obj,
        func.date(TelemetryRecord.observation_timestamp) <= end_date_obj,
    )

    if three_hour_intervals:
        query = query.where(
            extract("hour", TelemetryRecord.observation_timestamp).in_(
                [0, 3, 6, 9, 12, 15, 18, 21]
            )
        )

    query = (
        query
        .order_by(TelemetryRecord.observation_timestamp.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/{record_id}",
    response_model=TelemetryRecordResponse,
    summary="Получить конкретную запись по ID",
)
async def get_telemetry_record_by_id(
    record_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Возвращает одну запись метеоданных по её уникальному идентификатору."""

    result = await db.execute(
        select(TelemetryRecord).where(TelemetryRecord.id == record_id)
    )

    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    return record

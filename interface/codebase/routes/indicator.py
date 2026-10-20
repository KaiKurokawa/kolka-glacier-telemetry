"""
Маршруты API для индикатора состояния (светофор).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import IndicatorState
from ..database.session import async_session
from ..schemas.indicator import IndicatorResponse, IndicatorUpdate


router = APIRouter(prefix="/api/v1/indicator", tags=["Индикатор состояния"])


async def get_session():
    async with async_session() as session:
        yield session


@router.get(
    "/",
    response_model=IndicatorResponse,
    summary="Получить текущий уровень индикатора",
)
async def get_indicator(
    db: AsyncSession = Depends(get_session),
):
    """
    Возвращает текущий уровень светофора (1–5) и пояснение к нему.

    Фронтенд заливает кружки индикатора снизу вверх по значению level;
    при уровнях 4 и 5 дашборд дополнительно показывает плашку тревоги.
    """

    result = await db.execute(
        select(IndicatorState).order_by(IndicatorState.id.desc()).limit(1)
    )

    record = result.scalar_one_or_none()

    if record is None:
        # Возвращаем дефолтное состояние
        return IndicatorResponse(
            level=1,
            message=None,
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )

    return record


@router.put(
    "/",
    response_model=IndicatorResponse,
    summary="Установить уровень индикатора",
)
async def set_indicator(
    update: IndicatorUpdate,
    db: AsyncSession = Depends(get_session),
):
    """
    Устанавливает текущий уровень светофора (1–5) и необязательное пояснение.

    Операция идемпотентна: повторная установка того же уровня обновляет только updated_at и message.
    """

    # Получаем текущую запись
    result = await db.execute(
        select(IndicatorState).order_by(IndicatorState.id.desc()).limit(1)
    )

    record = result.scalar_one_or_none()

    if record is None:
        # Создаём новую запись
        record = IndicatorState(
            level=update.level,
            message=update.message,
        )
        db.add(record)
    else:
        # Обновляем существующую
        record.level = update.level
        record.message = update.message

    await db.commit()
    await db.refresh(record)

    return record

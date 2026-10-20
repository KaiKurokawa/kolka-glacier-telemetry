"""
Схемы Pydantic для индикатора состояния (светофор).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IndicatorResponse(BaseModel):
    """Текущее состояние индикатора (светофора)."""

    model_config = ConfigDict(from_attributes=True)

    level: int = Field(
        ge=1,
        le=5,
        description="Уровень индикатора: 1 — норма, 2 — внимание, 3 — предупреждение, 4 — высокая тревога, 5 — опасность",
    )

    message: str | None = Field(
        default=None,
        description="Пояснение к уровню (причина тревоги); null, если не задано",
    )

    updated_at: datetime = Field(
        description="Время последней установки уровня",
    )


class IndicatorUpdate(BaseModel):
    """Запрос на установку уровня индикатора."""

    level: int = Field(
        ge=1,
        le=5,
        description="Уровень индикатора от 1 до 5",
    )

    message: str | None = Field(
        default=None,
        max_length=300,
        description="Пояснение к уровню (необязательно)",
    )

"""
Схемы Pydantic для валидации и сериализации данных API.

Названия полей совпадают с именами, которые возвращает XML-парсер.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryRecordBase(BaseModel):
    """
    Базовая схема полей одной метеорологической сводки.
    Используется как основа для создания и ответа.
    """

    observation_timestamp: datetime = Field(
        description="Локальное время наблюдения",
    )

    station_identifier: str | None = Field(
        default=None,
        description="Идентификатор метеостанции",
    )

    latitude: float | None = Field(
        default=None,
        description="Широта станции, градусы",
    )

    longitude: float | None = Field(
        default=None,
        description="Долгота станции, градусы",
    )

    altitude: float | None = Field(
        default=None,
        description="Высота станции над уровнем моря, метры",
    )

    air_temperature_average_at_2m: float | None = None
    air_temperature_maximum_at_2m: float | None = None
    air_temperature_minimum_at_2m: float | None = None

    relative_humidity_average_at_2m: float | None = None

    atmospheric_pressure_average_at_mean_sea_level: float | None = None
    atmospheric_pressure_average_at_station: float | None = None

    wind_speed_average_at_10m: float | None = None
    wind_speed_maximum_at_10m: float | None = None
    wind_direction_average_at_10m: float | None = None

    precipitation_sum: float | None = None
    precipitation_accumulated: float | None = None
    precipitation_intensity_average_at_2m: float | None = None

    snow_depth_instantaneous: float | None = None
    snow_depth_average: float | None = None
    snow_depth_maximum: float | None = None
    snow_depth_minimum: float | None = None

    battery_instantaneous_voltage: float | None = None


class TelemetryRecordCreate(TelemetryRecordBase):
    """Схема для создания одной записи телеметрии."""

    pass


class TelemetryRecordResponse(TelemetryRecordBase):
    """Схема ответа API для одной записи телеметрии."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class TelemetryRecordBatchUpload(BaseModel):
    """Схема для пакетной загрузки метеоданных."""

    records: list[TelemetryRecordCreate] = Field(
        default_factory=list,
        description="Список записей телеметрии для загрузки",
    )


class TelemetryBatchUploadResult(BaseModel):
    """Схема результата пакетной загрузки."""

    inserted: int = Field(description="Количество добавленных записей")
    skipped: int = Field(description="Количество пропущенных дубликатов")
    total: int = Field(description="Общее количество записей в пакете")

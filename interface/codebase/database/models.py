"""
ORM-модели базы данных.
Описывает структуру таблиц для хранения метеорологических наблюдений, фотографий и индикатора состояния.
"""

from datetime import datetime, timezone, date

from sqlalchemy import DateTime, Date, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base


class TelemetryRecord(Base):
    """
    Модель одной метеорологической сводки.

    Каждая строка соответствует одному элементу <report> внутри XML-файла телеметрии.
    В одном файле может быть несколько сводок (например, каждые 10 минут).
    """

    __tablename__ = "kolka_telemetry"

    __table_args__ = (
        UniqueConstraint(
            "station_identifier",
            "observation_timestamp",
            name="uq_kolka_station_observation",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    observation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        index=True,
        nullable=False,
        comment="Локальное время наблюдения из секции <report>",
    )

    station_identifier: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
        comment="Идентификатор метеостанции (атрибут ID тега <station>)",
    )

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    altitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    air_temperature_average_at_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    air_temperature_maximum_at_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    air_temperature_minimum_at_2m: Mapped[float | None] = mapped_column(Float, nullable=True)

    relative_humidity_average_at_2m: Mapped[float | None] = mapped_column(Float, nullable=True)

    atmospheric_pressure_average_at_mean_sea_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    atmospheric_pressure_average_at_station: Mapped[float | None] = mapped_column(Float, nullable=True)

    wind_speed_average_at_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_maximum_at_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction_average_at_10m: Mapped[float | None] = mapped_column(Float, nullable=True)

    precipitation_sum: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_accumulated: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_intensity_average_at_2m: Mapped[float | None] = mapped_column(Float, nullable=True)

    snow_depth_instantaneous: Mapped[float | None] = mapped_column(Float, nullable=True)
    snow_depth_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    snow_depth_maximum: Mapped[float | None] = mapped_column(Float, nullable=True)
    snow_depth_minimum: Mapped[float | None] = mapped_column(Float, nullable=True)

    battery_instantaneous_voltage: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PhotoRecord(Base):
    """
    Модель метаданных фотографии с метеостанции.

    Структура имени файла: {camera_id}_{YYYY-MM-DD-HH-MM-SS}.JPG
    Пример: 1_2026-08-14-15-58-34.JPG

    У станции может быть несколько камер (обычно 4).
    Фотографии хранятся в MinIO, здесь только метаданные.
    """

    __tablename__ = "photo_records"

    __table_args__ = (
        UniqueConstraint("object_key", name="uq_photo_object_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    observation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        index=True,
        nullable=False,
        comment="Точное время съёмки, извлечённое из имени файла",
    )

    observation_date: Mapped[date] = mapped_column(
        Date,
        index=True,
        nullable=False,
        comment="Дата съёмки (для фильтрации по дням)",
    )

    camera_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
        comment="Номер камеры (первая цифра в имени файла)",
    )

    station_identifier: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
        comment="Идентификатор станции",
    )

    caption: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Подпись к фотографии",
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Оригинальное имя файла",
    )

    object_key: Mapped[str] = mapped_column(
        String(512),
        index=True,
        nullable=False,
        comment="Ключ объекта в MinIO (путь к файлу)",
    )

    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(127), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class IndicatorState(Base):
    """
    Модель состояния индикатора тревоги (светофор).

    Уровни:
    1 — норма
    2 — внимание
    3 — предупреждение
    4 — высокая тревога
    5 — опасность

    Хранится только одна запись (текущее состояние).
    """

    __tablename__ = "indicator_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Уровень индикатора от 1 до 5",
    )

    message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Пояснение к уровню (причина тревоги)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

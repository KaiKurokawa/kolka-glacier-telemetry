"""
Модуль инициализации подключения к базе данных.
Используется асинхронный движок SQLAlchemy.
"""

import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


# URL читается из переменных окружения, либо используется локальный дефолт
DATABASE_URL = os.getenv(
    "DATABASE_INTERFACE_DSN"
)


# Создание асинхронного движка
engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    pool_pre_ping=True
)


# Фабрика асинхронных сессий
async_session = async_sessionmaker(
    engine, 
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""
    pass

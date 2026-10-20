"""
Точка входа в приложение FastAPI.
Инициализирует программный интерфейс, подключает маршруты и управляет жизненным циклом приложения.
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database.session import Base, engine
from .routes.telemetry import router as telemetry_router
from .routes.photos import router as photos_router
from .routes.indicator import router as indicator_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Контекстный менеджер жизненного цикла приложения.
    Вызывается при старте и остановке сервера.
    """

    # При старте: автоматическое создание таблиц в базе данных, если их нет
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    # При остановке: очистка ресурсов (если необходимо)
    await engine.dispose()


# Инициализация экземпляра приложения
application = FastAPI(
    title="Метеостанция Колка — медиатека и индикатор состояния",
    description=(
        "Программный интерфейс для загрузки фотографий метеостанции, "
        "выдачи последних изображений для дашборда и управления индикатором состояния (светофор, уровни 1–5).\n\n"
        "Использование фронтендом: левая колонка дашборда (4 фоторамки) читает GET /api/v1/photos/latest?limit=4; "
        "правая колонка (светофор) читает GET /api/v1/indicator/ и отображает уровень заливкой кружков снизу вверх."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# Настройка CORS (разрешаем запросы с фронтенда)
application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Healthcheck на базовом уровне API
@application.get(
    "/api/v1/health/",
    tags=["Служебные"],
    summary="Проверить работоспособность программного интерфейса",
)
async def health_check():
    """
    Возвращает состояние готовности приложения.
    Используется контейнерной платформой для проверки здоровья сервиса.
    """

    return {"status": "ready", "timestamp": datetime.now().isoformat()}


application.include_router(telemetry_router)
application.include_router(photos_router)
application.include_router(indicator_router)

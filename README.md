# Kolka Telemetry — API доступа к телеметрии метеостанций ледника Колка

Программный интерфейс для работы с метеорологической телеметрией, получаемой с автоматических метеостанций, установленных в районе ледника Колка. Система предоставляет структурированный доступ к данным наблюдений и служит прослойкой между сырыми XML-файлами телеметрии и конечными потребителями данных.

Ледник Колка представляет собой пульсирующий ледник, который периодически совершает стремительные подвижки. Регулярный мониторинг метеорологических параметров в районе ледника позволяет отслеживать изменения условий, влияющих на его динамику, и своевременно реагировать на потенциально опасные ситуации.

---

## Содержание

- [Архитектура проекта](#архитектура-проекта)
- [Структура директорий](#структура-директорий)
- [Требования и зависимости](#требования-и-зависимости)
- [Переменные окружения](#переменные-окружения)
- [Быстрый старт](#быстрый-старт)
- [Проверка работоспособности](#проверка-работоспособности)
- [Доступные эндпоинты](#доступные-эндпоинты)
- [Тестовая загрузка данных](#тестовая-загрузка-данных)
- [Примеры использования](#примеры-использования)
- [Планы развития](#планы-развития)

---

## Архитектура проекта

Проект состоит из двух основных компонентов, работающих в контейнерной среде:

| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| `application-interface` | Python, FastAPI | Программный интерфейс для доступа к данным телеметрии |
| `database` | PostgreSQL | Хранение метеорологических наблюдений |

Взаимодействие компонентов:

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Потребители   │  HTTP   │ application-    │  SQL    │    database     │
│     данных      │ ──────► │   interface     │ ──────► │  (PostgreSQL)   │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                      ▲
                                      │ HTTP
                                      │
                            ┌─────────┴─────────┐
                            │  Источники данных  │
                            │   (ингестор)      │
                            └───────────────────┘
```

На текущем этапе проект предоставляет только программный интерфейс. Загрузка данных из внешних источников осуществляется вручную или будет автоматизирована в рамках отдельного компонента (см. [Планы развития](#планы-развития)).

---

## Структура директорий

```
kolka-glacier-telemetry-viewer-fastapi/
├── README.md                       # Настоящий файл
├── compose.yaml                    # Конфигурация Docker Compose
├── .env                            # Переменные окружения (не коммитится в git)
├── interface/                      # FastAPI приложение
│   ├── Dockerfile                  # Сборка образа приложения
│   ├── requirements.txt            # Python-зависимости
│   └── codebase/                   # Исходный код
│       ├── main.py                 # Точка входа приложения
│       ├── database/               # Работа с базой данных
│       │   ├── session.py          # Инициализация подключения
│       │   └── models.py           # ORM-модели
│       ├── routes/                 # HTTP-маршруты
│       │   └── telemetry.py        # Эндпоинты телеметрии
│       └── schemas/                # Pydantic-схемы
│           └── telemetry.py        # Схемы валидации и сериализации
└── database/                       # Данные базы данных
    └── data/
        └── bootstrap/              # SQL-скрипты инициализации
```

---

## Требования и зависимости

Для запуска проекта требуются:

- **Docker** версии 20.10 или выше
- **Docker Compose** версии 2.0 или выше
- **Свободные порты**: 3311 (интерфейс), 3313 (база данных)

Проект использует следующие технологии внутри контейнеров:

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Язык программирования | Python | 3.13 |
| Веб-фреймворк | FastAPI | актуальная |
| База данных | PostgreSQL | 17 |
| ORM | SQLAlchemy | 2.x |
| Асинхронный драйвер БД | asyncpg | актуальная |

---

## Переменные окружения

Все настройки проекта задаются через файл `.env` в корне проекта. Этот файл не должен коммититься в систему контроля версий.

### Общие настройки

| Переменная | Описание | Пример значения |
|-----------|----------|----------------|
| `TIME_ZONE` | Часовой пояс для контейнеров | `Europe/Moscow` |

### Приложение (интерфейс)

| Переменная | Описание | Пример значения |
|-----------|----------|----------------|
| `INTERFACE_HOST_PORT` | Порт на хосте для доступа к интерфейсу | `3311` |
| `INTERFACE_CONTAINER_PORT` | Порт внутри контейнера приложения | `8000` |

### База данных

| Переменная | Описание | Пример значения |
|-----------|----------|----------------|
| `DATABASE_INTERFACE_HOST_PORT` | Порт на хосте для доступа к БД | `3313` |
| `DATABASE_INTERFACE_CONTAINER_PORT` | Порт внутри контейнера БД | `5432` |
| `DATABASE_INTERFACE_HOST` | Адрес БД внутри сети контейнеров | `database` |
| `DATABASE_DEFAULT_NAME` | Имя базы данных | `kolka_telemetry` |
| `DATABASE_DEFAULT_USER` | Пользователь БД | `admin` |
| `DATABASE_DEFAULT_PASSWORD` | Пароль пользователя БД | — |
| `DATABASE_INTERFACE_DSN` | Строка соединения для асинхронных библиотек | `postgresql+asyncpg://user:pass@host:port/db` |

### Пример файла `.env`

```bash
# -------------------------------------------------------------------------
# Общие настройки
# -------------------------------------------------------------------------

TIME_ZONE=Europe/Moscow


# -------------------------------------------------------------------------
# Приложение
# -------------------------------------------------------------------------

INTERFACE_HOST_PORT=3311
INTERFACE_CONTAINER_PORT=8000


# -------------------------------------------------------------------------
# База данных
# -------------------------------------------------------------------------

DATABASE_INTERFACE_HOST_PORT=3313
DATABASE_INTERFACE_CONTAINER_PORT=5432

DATABASE_INTERFACE_HOST=database

DATABASE_DEFAULT_NAME=kolka_telemetry
DATABASE_DEFAULT_USER=admin
DATABASE_DEFAULT_PASSWORD=your-secure-password-here

DATABASE_INTERFACE_DSN=postgresql+asyncpg://${DATABASE_DEFAULT_USER}:${DATABASE_DEFAULT_PASSWORD}@database:${DATABASE_INTERFACE_CONTAINER_PORT}/${DATABASE_DEFAULT_NAME}
```

---

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <repository-url> kolka-glacier-telemetry-viewer-fastapi
cd kolka-glacier-telemetry-viewer-fastapi
```

### 2. Создание файла `.env`

Создайте файл `.env` в корне проекта на основе примера из раздела [Переменные окружения](#переменные-окружения).

### 3. Сборка и запуск

```bash
# Сборка образов
docker compose build

# Запуск в фоновом режиме
docker compose up -d

# Просмотр логов
docker compose logs -f
```

### 4. Проверка работоспособности

```bash
# Проверка healthcheck эндпоинта
curl http://localhost:3311/api/v1/health/

# Открытие интерактивной документации
open http://localhost:3311/docs
```

### Остановка проекта

```bash
# Остановка контейнеров
docker compose down

# Остановка с удалением томов данных
docker compose down -v
```

---

## Проверка работоспособности

### Статус контейнеров

```bash
docker compose ps
```

Ожидаемый вывод:

```
NAME                                        STATUS
kolka-glacier-telemetry-viewer-database-1   Up (healthy)
kolka-glacier-telemetry-viewer-interface-1  Up (healthy)
```

### Проверка эндпоинта здоровья

```bash
curl http://localhost:3311/api/v1/health/
```

Ожидаемый ответ:

```json
{
  "status": "ready",
  "timestamp": "2026-10-14T12:00:00.000000"
}
```

### Доступ к документации

Интерактивная документация (Swagger) доступна по адресу:

```
http://localhost:3311/docs
```

Альтернативная документация (ReDoc):

```
http://localhost:3311/redoc
```

---

## Доступные эндпоинты

### Базовые маршруты

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/health/` | Проверка работоспособности |
| `GET` | `/docs` | Интерактивная документация (Swagger) |
| `GET` | `/redoc` | Альтернативная документация |

### Телеметрия

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/telemetry/` | Получить список записей с фильтрацией |
| `GET` | `/api/v1/telemetry/{record_id}` | Получить конкретную запись по идентификатору |
| `POST` | `/api/v1/telemetry/upload` | Загрузить пакет метеоданных |

### Параметры фильтрации эндпоинта `GET /api/v1/telemetry/`

| Параметр | Тип | Описание |
|---------|-----|----------|
| `start_date` | `string` | Начальная дата в формате `YYYY-MM-DD`. По умолчанию сегодня |
| `end_date` | `string` | Конечная дата в формате `YYYY-MM-DD`. По умолчанию сегодня |
| `three_hour_intervals` | `boolean` | Только записи каждые 3 часа (00, 03, 06, 09, 12, 15, 18, 21). По умолчанию `false` |
| `limit` | `integer` | Максимальное количество записей. По умолчанию `100`, максимум `1000` |
| `offset` | `integer` | Смещение для пагинации. По умолчанию `0` |

---

## Тестовая загрузка данных

Для проверки работоспособности эндпоинта загрузки данных доступен следующий тестовый запрос. Этот запрос имитирует данные, которые в будущем будут поступать от автоматического ингестора телеметрии.

### Пример запроса

```bash
curl -X POST "http://localhost:3311/api/v1/telemetry/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "records": [
      {
        "observation_timestamp": "2026-10-14T15:00:00",
        "station_identifier": "77777",
        "latitude": 55.8623,
        "longitude": 37.4857,
        "altitude": 0,
        "wind_speed_average_at_10m": 0.3,
        "wind_speed_maximum_at_10m": 0.5,
        "wind_direction_average_at_10m": 147.0,
        "air_temperature_average_at_2m": 13.4,
        "air_temperature_maximum_at_2m": 13.4,
        "air_temperature_minimum_at_2m": 13.3,
        "relative_humidity_average_at_2m": 65.0,
        "atmospheric_pressure_average_at_station": 1011.6,
        "atmospheric_pressure_average_at_mean_sea_level": 1033.4,
        "battery_instantaneous_voltage": 45.2,
        "precipitation_intensity_average_at_2m": 0.0,
        "precipitation_sum": null,
        "precipitation_accumulated": 0.0,
        "snow_depth_instantaneous": 90.8,
        "snow_depth_average": 92.2,
        "snow_depth_maximum": 96.9,
        "snow_depth_minimum": 88.9
      },
      {
        "observation_timestamp": "2026-10-14T15:10:00",
        "station_identifier": "77777",
        "latitude": 55.8623,
        "longitude": 37.4857,
        "altitude": 0,
        "wind_speed_average_at_10m": 0.2,
        "wind_speed_maximum_at_10m": 0.6,
        "wind_direction_average_at_10m": 175.0,
        "air_temperature_average_at_2m": 13.1,
        "air_temperature_maximum_at_2m": 13.3,
        "air_temperature_minimum_at_2m": 13.0,
        "relative_humidity_average_at_2m": 66.0,
        "atmospheric_pressure_average_at_station": 1011.7,
        "atmospheric_pressure_average_at_mean_sea_level": 1033.4,
        "battery_instantaneous_voltage": 45.2,
        "precipitation_intensity_average_at_2m": 0.0,
        "precipitation_sum": null,
        "precipitation_accumulated": 0.0,
        "snow_depth_instantaneous": 91.1,
        "snow_depth_average": 90.5,
        "snow_depth_maximum": 92.3,
        "snow_depth_minimum": 88.9
      }
    ]
  }'
```

### Ожидаемый ответ при успешной загрузке

```json
{
  "inserted": 2,
  "skipped": 0,
  "total": 2
}
```

### Ожидаемый ответ при повторной загрузке тех же данных

Дубликаты записей определяются по комбинации `station_identifier` и `observation_timestamp`. При повторной загрузке тех же данных:

```json
{
  "inserted": 0,
  "skipped": 2,
  "total": 2
}
```

### Поля записи телеметрии

| Поле | Тип | Описание |
|------|-----|----------|
| `observation_timestamp` | `datetime` | Локальное время наблюдения |
| `station_identifier` | `string \| null` | Идентификатор метеостанции |
| `latitude` | `float \| null` | Широта станции, градусы |
| `longitude` | `float \| null` | Долгота станции, градусы |
| `altitude` | `float \| null` | Высота станции над уровнем моря, метры |
| `air_temperature_average_at_2m` | `float \| null` | Температура воздуха средняя, высота 2 м, °C |
| `air_temperature_maximum_at_2m` | `float \| null` | Температура воздуха максимальная, высота 2 м, °C |
| `air_temperature_minimum_at_2m` | `float \| null` | Температура воздуха минимальная, высота 2 м, °C |
| `relative_humidity_average_at_2m` | `float \| null` | Относительная влажность средняя, высота 2 м, % |
| `atmospheric_pressure_average_at_mean_sea_level` | `float \| null` | Давление приведённое к уровню моря, среднее, гПа |
| `atmospheric_pressure_average_at_station` | `float \| null` | Давление на станции, среднее, гПа |
| `wind_speed_average_at_10m` | `float \| null` | Скорость ветра средняя, высота 10 м, м/с |
| `wind_speed_maximum_at_10m` | `float \| null` | Скорость ветра максимальная, высота 10 м, м/с |
| `wind_direction_average_at_10m` | `float \| null` | Направление ветра среднее, высота 10 м, градусы |
| `precipitation_sum` | `float \| null` | Сумма осадков за интервал, мм |
| `precipitation_accumulated` | `float \| null` | Накопленные осадки, мм |
| `precipitation_intensity_average_at_2m` | `float \| null` | Интенсивность осадков средняя, мм/ч |
| `snow_depth_instantaneous` | `float \| null` | Высота снежного покрова мгновенная, см |
| `snow_depth_average` | `float \| null` | Высота снежного покрова средняя, см |
| `snow_depth_maximum` | `float \| null` | Высота снежного покрова максимальная, см |
| `snow_depth_minimum` | `float \| null` | Высота снежного покрова минимальная, см |
| `battery_instantaneous_voltage` | `float \| null` | Напряжение батареи, В |

---

## Примеры использования

### Получение всех записей за сегодня

```bash
curl "http://localhost:3311/api/v1/telemetry/"
```

### Получение записей за конкретную дату

```bash
curl "http://localhost:3311/api/v1/telemetry/?start_date=2026-10-14"
```

### Получение записей за диапазон дат

```bash
curl "http://localhost:3311/api/v1/telemetry/?start_date=2026-09-01&end_date=2026-09-30"
```

### Только трёхчасовые отметки за сегодня

```bash
curl "http://localhost:3311/api/v1/telemetry/?three_hour_intervals=true"
```

### Пагинация

```bash
curl "http://localhost:3311/api/v1/telemetry/?limit=50&offset=100"
```

### Получение конкретной записи

```bash
curl "http://localhost:3311/api/v1/telemetry/1"
```

---

## Планы развития

На текущем этапе проект содержит только программный интерфейс и базу данных. Планируются следующие расширения:

### Автоматический ингестор данных

Отдельный сервис, который будет выполнять следующие функции:

1. Периодическое подключение к внешнему источнику данных (протокол передачи телеметрии)
2. Поиск и загрузка архивов с данными наблюдений
3. Распаковка архивов и извлечение XML-файлов
4. Парсинг содержимого файлов телеметрии
5. Автоматическая отправка распарсенных данных в программный интерфейс
6. Обработка ошибок и повторные попытки загрузки

Ингестор будет работать по расписанию, соответствующему периодичности поступления данных с метеостанций.

### Визуализация данных

Веб-интерфейс для отображения телеметрии в виде графиков и диаграмм:

- Динамика температуры воздуха
- Изменение атмосферного давления
- Направление и скорость ветра
- Количество осадков и высота снежного покрова

### Система оповещений

Механизм уведомления при выходе параметров за допустимые пределы, что может свидетельствовать об изменениях в состоянии ледника.

---

## Дополнительная информация

### Полезные команды

```bash
# Просмотр логов конкретного сервиса
docker compose logs -f application-interface

# Вход в консоль контейнера базы данных
docker compose exec database psql -U admin -d kolka_telemetry

# Пересоздание базы данных (удаляет все данные)
docker compose exec database psql -U admin -d kolka_telemetry -c "DROP TABLE IF EXISTS kolka_telemetry CASCADE;"

# Пересборка образа приложения
docker compose build --no-cache application-interface

# Просмотр переменных окружения внутри контейнера
docker compose exec application-interface env
```

### Структура таблицы базы данных

Таблица `kolka_telemetry` хранит метеорологические наблюдения со следующими характеристиками:

- Каждая запись соответствует одной секции `<report>` из исходного XML-файла телеметрии
- Уникальность записи обеспечивается комбинацией `station_identifier` и `observation_timestamp`
- Временные метки хранятся в локальном времени станции
- Все метеорологические параметры допускают отсутствие данных (значения `NULL`)

### Контактная информация

Для вопросов по проекту обращаться к администратору репозитория.

---

*Документация обновлена: 2026-10-14*
# kolka-glacier-telemetry

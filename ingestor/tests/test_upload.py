"""
Тестовый скрипт загрузки XML-файлов телеметрии в API.

Читает XML-файлы из указанной папки, парсит их и отправляет в программный
интерфейс для сохранения в базу данных.

Использование:
    python test_upload.py /путь/к/папке/с/файлами

Опции:
    --api-url URL    Адрес API (по умолчанию http://localhost:3311)
    --dry-run        Только парсинг без отправки в API
    --verbose        Подробный вывод каждого запроса
"""

import sys
import glob
import argparse
import traceback
from pathlib import Path
from datetime import datetime, date
from typing import Any

import httpx

# Добавляем путь к codebase, чтобы импортировать парсер
sys.path.insert(0, str(Path(__file__).parent / "application" / "codebase"))

from ..codebase.helpers.xml_parser import parse_telemetry_xml


# -------------------------------------------------------------------------
# Цветной вывод
# -------------------------------------------------------------------------

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_success(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def print_info(message: str):
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


def print_header(title: str):
    print(f"\n{Colors.BOLD}{title}{Colors.RESET}")
    print("=" * 80)


# -------------------------------------------------------------------------
# Сериализация данных для отправки в API
# -------------------------------------------------------------------------

def _serialize_value(value: Any) -> Any:
    """
    Приводит значение к JSON-совместимому виду.

    Python-объекты datetime/date не сериализуются стандартным json.dumps(),
    поэтому явно преобразуем их в ISO-строки.
    """

    if isinstance(value, datetime):
        # isoformat вернёт "2026-09-29T15:00:00" — то, что ожидает Pydantic
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return value


def _serialize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Приводит все записи к JSON-совместимому виду.
    """

    return [
        {key: _serialize_value(value) for key, value in record.items()}
        for record in records
    ]


# -------------------------------------------------------------------------
# Проверка доступности API
# -------------------------------------------------------------------------

def check_api_health(api_url: str, timeout: float = 5.0) -> bool:
    """
    Проверяет доступность API через healthcheck эндпоинт.
    """

    health_url = f"{api_url}/api/v1/health/"

    try:
        response = httpx.get(health_url, timeout=timeout)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ready":
                print_success(f"API доступен: {health_url}")
                return True

        print_error(f"API вернул неожиданный ответ: {response.status_code}")
        return False

    except httpx.RequestError as error:
        print_error(f"Не удалось подключиться к API: {error}")
        return False

    except Exception as error:
        print_error(f"Ошибка при проверке API: {error}")
        return False


# -------------------------------------------------------------------------
# Отправка данных в API
# -------------------------------------------------------------------------

def upload_records_to_api(
    records: list[dict[str, Any]],
    api_url: str,
    timeout: float = 30.0,
    verbose: bool = False,
) -> dict[str, int]:
    """
    Отправляет список записей в API и возвращает статистику.
    """

    upload_url = f"{api_url}/api/v1/telemetry/upload"

    # Ключевой шаг: сериализуем datetime в ISO-строки
    serialized_records = _serialize_records(records)
    payload = {"records": serialized_records}

    try:
        response = httpx.post(upload_url, json=payload, timeout=timeout)

        if response.status_code == 200:
            result = response.json()
            return {
                "inserted": result.get("inserted", 0),
                "skipped": result.get("skipped", 0),
                "total": result.get("total", 0),
                "errors": 0,
            }

        # Неожидаемый статус — печатаем тело ответа, чтобы видеть детали
        print_error(f"API вернул ошибку: {response.status_code}")
        error_text = response.text[:500]
        print(f"   Ответ: {error_text}")

        return {
            "inserted": 0,
            "skipped": 0,
            "total": len(records),
            "errors": 1,
        }

    except httpx.RequestError as error:
        print_error(f"Ошибка сети при отправке: {error}")
        return {
            "inserted": 0,
            "skipped": 0,
            "total": len(records),
            "errors": 1,
        }

    except Exception as error:
        print_error(f"Непредвиденная ошибка: {error}")
        if verbose:
            traceback.print_exc()
        return {
            "inserted": 0,
            "skipped": 0,
            "total": len(records),
            "errors": 1,
        }


# -------------------------------------------------------------------------
# Обработка одного файла
# -------------------------------------------------------------------------

def process_file(
    file_path: Path,
    api_url: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, int]:
    """
    Обрабатывает один XML-файл: парсит и отправляет в API.
    """

    stats = {
        "records_parsed": 0,
        "inserted": 0,
        "skipped": 0,
        "errors": 0,
    }

    try:
        xml_content = file_path.read_text(encoding="utf-8")
        records = parse_telemetry_xml(xml_content)
        stats["records_parsed"] = len(records)

        if not records:
            print_warning(f"Файл не содержит записей: {file_path.name}")
            return stats

        if verbose:
            print_info(f"Распарсено {len(records)} записей")

        if dry_run:
            print_info(f"[DRY RUN] Пропуск отправки {len(records)} записей")
            stats["inserted"] = len(records)
        else:
            result = upload_records_to_api(
                records,
                api_url,
                verbose=verbose,
            )
            stats["inserted"] = result["inserted"]
            stats["skipped"] = result["skipped"]
            stats["errors"] = result["errors"]

            if result["errors"] == 0:
                print_success(
                    f"Отправлено: {result['inserted']} добавлено, "
                    f"{result['skipped']} пропущено"
                )

    except Exception as error:
        print_error(f"Ошибка обработки файла {file_path.name}: {error}")
        if verbose:
            traceback.print_exc()
        stats["errors"] += 1

    return stats


# -------------------------------------------------------------------------
# Главная функция
# -------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Загрузка XML-файлов телеметрии в API",
    )

    parser.add_argument("path", help="Путь к папке с XML-файлами или glob-шаблон")
    parser.add_argument(
        "--api-url",
        default="http://localhost:3311",
        help="Базовый URL API (по умолчанию: http://localhost:3311)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только парсинг без отправки в API",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Подробный вывод",
    )

    args = parser.parse_args()

    print_header("🚀 Загрузка XML-файлов телеметрии в API")

    path_pattern = args.path

    if "*" in path_pattern or "?" in path_pattern:
        file_paths = sorted(Path(p) for p in glob.glob(path_pattern))
    else:
        directory = Path(path_pattern)
        if not directory.is_dir():
            print_error(f"Путь не существует или не является папкой: {directory}")
            sys.exit(1)
        file_paths = sorted(directory.glob("*.xml"))

    if not file_paths:
        print_warning(f"Не найдено XML-файлов по пути: {path_pattern}")
        sys.exit(1)

    print_info(f"Найдено файлов: {len(file_paths)}")
    print_info(f"API: {args.api_url}")

    if args.dry_run:
        print_warning("Режим DRY RUN: данные не будут отправлены в API")

    if not args.dry_run:
        print()
        if not check_api_health(args.api_url):
            print_error("API недоступен. Прерывание.")
            sys.exit(1)

    print()
    print_header(f"📄 Обработка {len(file_paths)} файлов")

    total_stats = {
        "files_processed": 0,
        "files_with_errors": 0,
        "records_parsed": 0,
        "inserted": 0,
        "skipped": 0,
        "errors": 0,
    }

    for index, file_path in enumerate(file_paths, start=1):
        print(f"\n[{index}/{len(file_paths)}] {file_path.name}")
        print("-" * 80)

        stats = process_file(
            file_path,
            args.api_url,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        total_stats["files_processed"] += 1
        total_stats["records_parsed"] += stats["records_parsed"]
        total_stats["inserted"] += stats["inserted"]
        total_stats["skipped"] += stats["skipped"]
        total_stats["errors"] += stats["errors"]

        if stats["errors"] > 0:
            total_stats["files_with_errors"] += 1

    print_header("📋 Итоговая статистика")

    print(f"   Файлов обработано: {total_stats['files_processed']}")
    print(f"   Файлов с ошибками: {total_stats['files_with_errors']}")
    print(f"   Записей распарсено: {total_stats['records_parsed']}")

    if not args.dry_run:
        print(f"   Записей добавлено: {total_stats['inserted']}")
        print(f"   Записей пропущено: {total_stats['skipped']}")
        print(f"   Ошибок API: {total_stats['errors']}")

    print()

    if total_stats["files_with_errors"] > 0 or total_stats["errors"] > 0:
        print_warning("Завершено с ошибками")
        sys.exit(1)
    else:
        print_success("Завершено успешно")
        sys.exit(0)


if __name__ == "__main__":
    main()

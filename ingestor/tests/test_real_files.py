"""
Тест парсера на реальных XML-файлах телеметрии.

Использование:
    python test_real_files.py /путь/к/папке/с/файлами

Или через glob-шаблон:
    python test_real_files.py "./downloads/*.xml"
"""

import sys
import glob
from pathlib import Path
from datetime import datetime

# Добавляем путь к codebase, чтобы импортировать парсер
sys.path.insert(0, str(Path(__file__).parent / "application" / "codebase"))

from ..codebase.helpers.xml_parser import parse_telemetry_xml


# -------------------------------------------------------------------------
# Красивый вывод
# -------------------------------------------------------------------------

def print_separator(char="─", length=80):
    print(char * length)


def print_header(title: str):
    print_separator("═")
    print(f" {title} ".center(80, "═"))
    print_separator("═")


def print_report_summary(record: dict, index: int):
    """Печатает краткое резюме одного report-а."""
    
    timestamp = record.get("observation_timestamp")
    station = record.get("station_identifier", "?")
    
    time_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
    
    print(f"\n📊 Report #{index} | Станция: {station} | Время: {time_str}")
    print_separator()
    
    # Группируем поля по категориям для читаемости
    categories = {
        "🌡️ Температура": [],
        "💨 Ветер": [],
        "💧 Влажность и осадки": [],
        "📏 Давление": [],
        "❄️ Снег": [],
        "🔋 Питание": [],
        "📍 Станция": [],
        "🔧 Прочее": [],
    }
    
    for key, value in record.items():
        if value is None:
            continue
            
        # Распределяем по категориям
        if "temperature" in key:
            categories["🌡️ Температура"].append((key, value))
        elif "wind" in key:
            categories["💨 Ветер"].append((key, value))
        elif "humidity" in key or "precipitation" in key:
            categories["💧 Влажность и осадки"].append((key, value))
        elif "pressure" in key:
            categories["📏 Давление"].append((key, value))
        elif "snow" in key:
            categories["❄️ Снег"].append((key, value))
        elif "battery" in key:
            categories["🔋 Питание"].append((key, value))
        elif key in ("station_identifier", "latitude", "longitude", "altitude", "observation_timestamp"):
            categories["📍 Станция"].append((key, value))
        else:
            categories["🔧 Прочее"].append((key, value))
    
    # Выводим по категориям
    for category_name, fields in categories.items():
        if not fields:
            continue
            
        print(f"\n  {category_name}")
        for field_name, field_value in fields:
            # Форматируем значение
            if isinstance(field_value, float):
                value_str = f"{field_value:.2f}"
            else:
                value_str = str(field_value)
            
            print(f"    {field_name:50s} = {value_str}")


def print_file_statistics(file_path: Path, records: list):
    """Показывает статистику по файлу."""
    
    print(f"\n📈 Статистика файла:")
    print(f"   Количество report-ов: {len(records)}")
    
    if not records:
        return
    
    # Диапазон времени
    timestamps = [r.get("observation_timestamp") for r in records if isinstance(r.get("observation_timestamp"), datetime)]
    if timestamps:
        print(f"   Первое наблюдение: {min(timestamps).isoformat()}")
        print(f"   Последнее наблюдение: {max(timestamps).isoformat()}")
    
    # Все станции в файле
    stations = set(r.get("station_identifier") for r in records if r.get("station_identifier"))
    print(f"   Станций в файле: {', '.join(stations) if stations else 'не указано'}")
    
    # Подсчёт заполненных полей
    all_fields = set()
    for r in records:
        all_fields.update(r.keys())
    
    filled_count = sum(
        1 for field in all_fields 
        if any(r.get(field) is not None for r in records)
    )
    print(f"   Уникальных полей: {len(all_fields)}")
    print(f"   Полей с данными: {filled_count}")


# -------------------------------------------------------------------------
# Главная логика
# -------------------------------------------------------------------------

def process_file(file_path: Path, show_details: bool = True) -> int:
    """
    Обрабатывает один XML-файл и выводит результаты.
    
    Возвращает количество распарсенных report-ов.
    """
    
    print_header(f"📄 Файл: {file_path.name}")
    print(f"   Путь: {file_path}")
    print(f"   Размер: {file_path.stat().st_size / 1024:.1f} КБ")
    
    try:
        # Читаем содержимое файла
        xml_content = file_path.read_text(encoding="utf-8")
        
        # Парсим
        records = parse_telemetry_xml(xml_content)
        
        # Статистика
        print_file_statistics(file_path, records)
        
        # Детальный вывод каждого report-а
        if show_details:
            for index, record in enumerate(records, start=1):
                print_report_summary(record, index)
        else:
            print(f"\n   ℹ️  Детальный вывод пропущен (найдено {len(records)} report-ов)")
        
        return len(records)
    
    except Exception as error:
        print(f"\n   ❌ Ошибка обработки: {error}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python test_real_files.py <путь_к_папке_или_glob>")
        print()
        print("Примеры:")
        print("  python test_real_files.py ./downloads")
        print("  python test_real_files.py '/data/meteo/*.xml'")
        print("  python test_real_files.py ./downloads --brief")
        print()
        print("Опции:")
        print("  --brief    Показать только статистику, без деталей каждого report-а")
        sys.exit(1)
    
    # Разбираем аргументы
    args = sys.argv[1:]
    brief_mode = "--brief" in args
    if brief_mode:
        args.remove("--brief")
    
    path_pattern = args[0]
    
    # Определяем список файлов
    if "*" in path_pattern or "?" in path_pattern:
        # Это glob-шаблон
        file_paths = sorted(Path(p) for p in glob.glob(path_pattern))
    else:
        # Это папка
        directory = Path(path_pattern)
        if not directory.is_dir():
            print(f"❌ Путь не существует или не является папкой: {directory}")
            sys.exit(1)
        
        file_paths = sorted(directory.glob("*.xml"))
    
    if not file_paths:
        print(f"⚠️  Не найдено XML-файлов по пути: {path_pattern}")
        sys.exit(1)
    
    print_header(f"🚀 Запуск парсера на {len(file_paths)} файлах")
    print()
    
    # Обрабатываем файлы
    total_records = 0
    total_files = 0
    
    for file_path in file_paths:
        records_count = process_file(file_path, show_details=not brief_mode)
        total_records += records_count
        total_files += 1
        print()  # Пустая строка между файлами
    
    # Итоговая статистика
    print_header("📋 Итоги")
    print(f"   Обработано файлов: {total_files}")
    print(f"   Распарсено report-ов: {total_records}")
    if total_files > 0:
        print(f"   Среднее report-ов на файл: {total_records / total_files:.1f}")


if __name__ == "__main__":
    main()
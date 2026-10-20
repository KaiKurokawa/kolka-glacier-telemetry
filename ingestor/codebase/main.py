"""
Главный оркестратор цикла обработки телеметрии.

Запускается по расписанию через supercronic. Выполняет четыре последовательные фазы:
1. Распаковка архивов bzip2 → XML. Оригинал .bz2 удаляется после успешной распаковки.
2. Парсинг всех XML-файлов в директории.
3. Отправка распарсенных данных в программный интерфейс.
4. Обработка JPG-фотографий: скачивание, парсинг имён, пакетная отправка в API.

ВАЖНО: XML-файлы НЕ удаляются с FTP после успешной отправки. 
Они остаются на сервере как резервная копия и журнал обработанных данных.
"""

import logging
import sys
import tempfile
from pathlib import Path

from . import configuration

from .helpers.api_client import check_health, upload_records, upload_photos_to_api
from .helpers.filename_parser import parse_jpg_filename
from .helpers.archive_tools import decompress_bzip_archive
from .helpers.ftp_client import FTPClient
from .helpers.xml_parser import parse_telemetry_xml


logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Инициализация логирования
# -------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)


# -------------------------------------------------------------------------
# Фаза 1: распаковка архивов
# -------------------------------------------------------------------------

def process_bzip_archives(ftp: FTPClient) -> int:
    """
    Находит все .bz2 архивы, распаковывает их в XML,
    загружает XML обратно на FTP и удаляет оригинальные архивы .bz2.
    """

    filenames = ftp.list_files()
    archive_filenames = [f for f in filenames if f.lower().endswith(".bz2")]

    if not archive_filenames:
        logger.info("🔍 Архивов bzip2 не обнаружено.")
        return 0

    logger.info(f"📦 Найдено архивов для распаковки: {len(archive_filenames)}")

    processed_count = 0

    for archive_filename in archive_filenames:
        xml_filename = archive_filename[:-4]  # убираем ".bz2"
        logger.info(f"⚙️ Обработка: {archive_filename}")

        temporary_bzip_path: Path | None = None
        temporary_xml_path: Path | None = None

        try:
            # 1. Создаём временные файлы
            with tempfile.NamedTemporaryFile(delete=False, suffix=".bz2") as tmp_bz2:
                temporary_bzip_path = Path(tmp_bz2.name)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_xml:
                temporary_xml_path = Path(tmp_xml.name)

            # 2. Скачиваем архив
            ftp.download_file(archive_filename, temporary_bzip_path)

            # 3. Распаковываем (если здесь будет ошибка, архив не удалится)
            decompress_bzip_archive(temporary_bzip_path, temporary_xml_path)

            # 4. Загружаем XML на сервер
            ftp.upload_file(temporary_xml_path, xml_filename)
            logger.info(f"📤 XML успешно загружен на FTP: {xml_filename}")

            # 5. Удаляем оригинальный архив ТОЛЬКО после успешной распаковки и загрузки XML
            if configuration.DELETE_PROCESSED_ARCHIVES:
                ftp.delete_file(archive_filename)
                logger.info(f"🗑️ Оригинальный архив удалён: {archive_filename}")

            processed_count += 1
            logger.info(f"✅ Архив обработан: {archive_filename}")

        except Exception as error:
            logger.error(f"💥 Ошибка обработки {archive_filename}: {error}")

        finally:
            # Гарантированная очистка локальных временных файлов
            if temporary_bzip_path and temporary_bzip_path.exists():
                temporary_bzip_path.unlink()

            if temporary_xml_path and temporary_xml_path.exists():
                temporary_xml_path.unlink()

    return processed_count


# -------------------------------------------------------------------------
# Фаза 2 и 3: парсинг XML и отправка в API
# -------------------------------------------------------------------------

def process_xml_files(ftp: FTPClient) -> dict[str, int]:
    """
    Находит все .xml файлы, парсит каждый и отправляет записи в API.
    XML-файлы НЕ удаляются с FTP после успешной отправки (служат резервной копией).
    """

    filenames = ftp.list_files()
    xml_filenames = [f for f in filenames if f.lower().endswith(".xml")]

    if not xml_filenames:
        logger.info("🔍 XML-файлов для обработки не обнаружено.")
        return {
            "files_processed": 0,
            "files_with_errors": 0,
            "records_parsed": 0,
            "records_inserted": 0,
            "records_skipped": 0,
        }

    logger.info(f"📄 Найдено XML-файлов для отправки в API: {len(xml_filenames)}")

    totals = {
        "files_processed": 0,
        "files_with_errors": 0,
        "records_parsed": 0,
        "records_inserted": 0,
        "records_skipped": 0,
    }

    temporary_xml_path: Path | None = None

    for xml_filename in xml_filenames:
        logger.info(f"⚙️ Обработка XML: {xml_filename}")

        try:
            # 1. Создаём временный файл и скачиваем XML
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_xml:
                temporary_xml_path = Path(tmp_xml.name)

            ftp.download_file(xml_filename, temporary_xml_path)

            # 2. Парсим
            xml_content = temporary_xml_path.read_text(encoding="utf-8")
            records = parse_telemetry_xml(xml_content)
            totals["records_parsed"] += len(records)

            if not records:
                logger.warning(f"⚠️ Файл не содержит записей: {xml_filename}")
                totals["files_processed"] += 1
                continue

            logger.info(f"   Распарсено записей: {len(records)}")

            # 3. Отправляем в API
            result = upload_records(records)

            if result["success"]:
                totals["records_inserted"] += result["inserted"]
                totals["records_skipped"] += result["skipped"]

                logger.info(
                    f"   API: добавлено {result['inserted']}, "
                    f"пропущено (дубликаты) {result['skipped']}"
                )
                
                # ВАЖНО: XML остаётся на FTP как журнал и резервная копия.

                totals["files_processed"] += 1
                logger.info(f"✅ XML успешно обработан и отправлен: {xml_filename}")

            else:
                # API недоступен или вернул ошибку → оставляем XML на FTP для следующей попытки
                logger.warning(
                    f"⚠️ API не принял данные. XML оставлен на сервере: {xml_filename}"
                )

                totals["files_with_errors"] += 1

        except Exception as error:
            logger.error(f"💥 Ошибка обработки {xml_filename}: {error}")
            totals["files_with_errors"] += 1

        finally:
            if temporary_xml_path and temporary_xml_path.exists():
                temporary_xml_path.unlink()
                temporary_xml_path = None

    return totals


# -------------------------------------------------------------------------
# Фаза 4: обработка JPG-фотографий
# -------------------------------------------------------------------------

def process_jpg_files(ftp: FTPClient) -> dict[str, int]:
    """
    Находит все .jpg файлы в директории фотографий, парсит имена,
    скачивает и отправляет в API пакетом для сохранения в MinIO.
    
    Имя файла формата: {camera_id}_{YYYY-MM-DD-HH-MM-SS}.JPG
    Пример: 2_2026-08-14-16-42-16.JPG
    
    Успешно отправленные файлы НЕ удаляются с FTP (служат резервной копией).
    """
    
    # Переходим в корень FTP, чтобы поддержать как абсолютные, так и относительные пути
    try:
        ftp.change_directory("/")
    except Exception as error:
        logger.warning(f"⚠️ Не удалось перейти в корень FTP: {error}")
    
    # Переходим в директорию с фотографиями
    try:
        ftp.change_directory(configuration.FTP_JPG_PATH)

    except Exception as error:
        logger.error(f"💥 Не удалось перейти в директорию фотографий: {error}")
        return {
            "files_processed": 0,
            "files_with_errors": 0,
            "files_uploaded": 0,
        }

    filenames = ftp.list_files()
    jpg_filenames = [
        f for f in filenames
        if f.lower().endswith((".jpg", ".jpeg"))
    ]

    if not jpg_filenames:
        logger.info("🔍 JPG-файлов для обработки не обнаружено.")
        return {
            "files_processed": 0,
            "files_with_errors": 0,
            "files_uploaded": 0,
        }

    logger.info(f"📷 Найдено JPG-файлов для отправки в API: {len(jpg_filenames)}")

    totals = {
        "files_processed": 0,
        "files_with_errors": 0,
        "files_uploaded": 0,
    }

    # Собираем все фотографии в пакет
    photos_batch: list[dict] = []
    temporary_jpg_path: Path | None = None

    for jpg_filename in jpg_filenames:
        logger.info(f"⚙️ Обработка JPG: {jpg_filename}")

        # Парсим имя файла
        parsed = parse_jpg_filename(jpg_filename)

        if parsed is None:
            logger.warning(
                f"⚠️ Не удалось распознать имя файла: {jpg_filename}. Пропускаем."
            )
            totals["files_with_errors"] += 1
            continue

        logger.info(
            f"   Камера: {parsed.camera_id}, "
            f"Время: {parsed.observation_timestamp.isoformat()}"
        )

        try:
            # 1. Создаём временный файл и скачиваем JPG
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_jpg:
                temporary_jpg_path = Path(tmp_jpg.name)

            ftp.download_file(jpg_filename, temporary_jpg_path)

            # 2. Читаем содержимое
            file_bytes = temporary_jpg_path.read_bytes()

            if not file_bytes:
                logger.warning(f"⚠️ Пустой файл: {jpg_filename}")
                totals["files_with_errors"] += 1
                continue

            # 3. Добавляем в пакет
            photos_batch.append({
                "filename": jpg_filename,
                "file_bytes": file_bytes,
                "observation_timestamp": parsed.observation_timestamp.isoformat(),
                "camera_id": parsed.camera_id,
            })

        except Exception as error:
            logger.error(f"💥 Ошибка обработки {jpg_filename}: {error}")
            totals["files_with_errors"] += 1

        finally:
            if temporary_jpg_path and temporary_jpg_path.exists():
                temporary_jpg_path.unlink()
                temporary_jpg_path = None

    # Отправляем весь пакет в API
    if photos_batch:
        logger.info(f"📤 Отправка пакета из {len(photos_batch)} фотографий в API...")

        result = upload_photos_to_api(
            photos=photos_batch,
            station_id=configuration.DEFAULT_STATION_ID,
            caption="Автоматическая загрузка с FTP",
        )

        if result is not None:
            inserted_count = result.get("inserted", 0)
            skipped_count = result.get("skipped", 0)
            
            totals["files_uploaded"] = inserted_count
            totals["files_processed"] = inserted_count + skipped_count

            logger.info(
                f"✅ Пакет отправлен: добавлено {inserted_count}, "
                f"пропущено (дубликаты) {skipped_count}"
            )
        else:
            # API недоступен или вернул ошибку → оставляем JPG на FTP
            logger.warning("⚠️ API не принял пакет фотографий. Файлы оставлены на сервере.")
            totals["files_with_errors"] += len(photos_batch)

    # Возвращаемся в корень, а потом в основную директорию телеметрии
    try:
        ftp.change_directory("/")
        ftp.change_directory(configuration.FTP_TELEMETRY_PATH)
    except Exception:
        pass

    return totals


# -------------------------------------------------------------------------
# Главный цикл
# -------------------------------------------------------------------------

def run_processing_cycle() -> None:
    """Выполняет один полный цикл обработки телеметрии."""

    if not check_health():
        logger.error("❌ API недоступен. Цикл обработки прерван.")
        return

    ftp = FTPClient()

    try:
        ftp.connect()
        ftp.change_directory(configuration.FTP_TELEMETRY_PATH)

        # Фаза 1: распаковка архивов
        archives_processed = process_bzip_archives(ftp)
        logger.info(f"📦 Распаковано архивов: {archives_processed}")

        # Фазы 2+3: парсинг XML и отправка в API
        xml_stats = process_xml_files(ftp)

        logger.info(
            f"📄 Итог по XML: обработано {xml_stats['files_processed']}, "
            f"с ошибками {xml_stats['files_with_errors']}, "
            f"распарсено записей {xml_stats['records_parsed']}, "
            f"добавлено в БД {xml_stats['records_inserted']}, "
            f"пропущено (дубли) {xml_stats['records_skipped']}"
        )

        # Фаза 4: обработка JPG-фотографий
        jpg_stats = process_jpg_files(ftp)

        logger.info(
            f"📷 Итог по JPG: обработано {jpg_stats['files_processed']}, "
            f"с ошибками {jpg_stats['files_with_errors']}, "
            f"загружено {jpg_stats['files_uploaded']}"
        )

    finally:
        ftp.close()


# -------------------------------------------------------------------------
# Точка входа
# -------------------------------------------------------------------------

def main() -> None:
    """Запускает один цикл обработки телеметрии."""

    logger.info("🚀 Запуск цикла обработки телеметрии.")
    logger.info(f"   FTP: {configuration.FTP_HOST_ADDRESS}/{configuration.FTP_TELEMETRY_PATH}")
    logger.info(f"   API: {configuration.API_BASE_URL}")

    try:
        run_processing_cycle()
        logger.info("🏁 Цикл обработки завершён.")

    except Exception as error:
        logger.error(f"⚠️ Критическая ошибка цикла: {error}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

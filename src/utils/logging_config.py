"""
Конфигурация логирования для проекта WBParser.

Обеспечивает ротацию логов, разделение по уровням и JSON-форматирование.
Использует RotatingFileHandler для ограничения размера файлов и поддержку
структурированных логов через python-json-logger.

"""

import logging
import logging.handlers
import sys

from pythonjsonlogger.json import JsonFormatter

from src.config.app_settings import settings


def setup_logging() -> None:
    """
    Настраивает глобальное логирование приложения.

    Создаёт три обработчика:
    1. RotatingFileHandler для общего лога (app.log) с ротацией по размеру.
    2. RotatingFileHandler для ошибок (errors.log) уровня ERROR и выше.
    3. StreamHandler для вывода в консоль.

    Формат логов выбирается на основе settings.log_format_json:
    - Если True, используется JSON-форматирование.
    - Если False, используется текстовый формат из settings.log_format.

    Уровень логирования задаётся через settings.log_level.
    """
    logs_dir = settings.ensure_logs_dir()
    log_level = getattr(logging, settings.log_level.upper())

    # Получаем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Очищаем существующие обработчики, чтобы избежать дублирования
    root_logger.handlers.clear()

    # Создаём обработчики
    handlers = []

    # Общий файловый лог с ротацией
    app_log_path = logs_dir / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=app_log_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    handlers.append(file_handler)

    # Отдельный файл для ошибок (если включено)
    if settings.log_separate_error_file:
        error_log_path = logs_dir / "errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_path,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        handlers.append(error_handler)

    # Консольный вывод
    console_handler = logging.StreamHandler(sys.stdout)
    handlers.append(console_handler)

    # Выбираем форматтер
    if settings.log_format_json:
        formatter = create_json_formatter()
    else:
        formatter = create_text_formatter()

    # Применяем форматтер ко всем обработчикам
    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Логирование успешной настройки
    logging.info(
        "Логирование настроено. Уровень: %s, JSON: %s, ротация: %d МБ, "
        "резервных копий: %d",
        settings.log_level,
        settings.log_format_json,
        settings.log_max_bytes // (1024 * 1024),
        settings.log_backup_count,
    )


def create_json_formatter() -> JsonFormatter:
    """
    Создаёт JSON-форматтер для структурированных логов.

    Returns:
        JsonFormatter: Форматтер, который преобразует записи логов
        в JSON-строки.
    """
    # Определяем поля, которые будут включены в JSON
    json_fields = [
        "asctime",
        "levelname",
        "name",
        "module",
        "funcName",
        "lineno",
        "message",
        "exc_info",
    ]
    json_format = " ".join(f"%({field})s" for field in json_fields)

    formatter = JsonFormatter(
        fmt=json_format,
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
            "module": "module",
            "funcName": "function",
            "lineno": "line",
            "message": "message",
            "exc_info": "exception",
        },
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return formatter


def create_text_formatter() -> logging.Formatter:
    """
    Создаёт текстовый форматтер на основе настроек приложения.

    Returns:
        logging.Formatter: Текстовый форматтер.
    """
    return logging.Formatter(
        fmt=settings.log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Возвращает логгер с заданным именем.

    Удобная обёртка для стандартного logging.getLogger, которая гарантирует,
    что логирование уже настроено.

    Args:
        name: Имя логгера (обычно __name__). Если None, возвращается
        корневой логгер.

    Returns:
        logging.Logger: Настроенный логгер.
    """
    # Если логирование ещё не настроено, настраиваем его
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        setup_logging()
    return logging.getLogger(name)

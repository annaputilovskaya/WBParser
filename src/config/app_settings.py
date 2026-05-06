"""
Конфигурация приложения на основе pydantic-settings.

Все настройки загружаются из переменных окружения с поддержкой .env файла.
Используется валидация типов и значений через pydantic.

Пример .env файла:
    WB_BASE_URL=https://www.wildberries.ru
    WB_API_SEARCH_URL=https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search
    REQUEST_TIMEOUT=10
    DELAY_BETWEEN_REQUESTS=0.3
    MAX_RETRIES=3
    LOG_LEVEL=INFO
    LOG_FORMAT_JSON=false
    LOG_MAX_BYTES=10485760
    LOG_BACKUP_COUNT=5
    SENTRY_DSN=
    USER_AGENT_ROTATION=true
    PROXY_POOL=
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Настройки приложения с валидацией и поддержкой .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="WB_",
        case_sensitive=False,
        extra="ignore",
    )

    # Базовые URL Wildberries
    base_url: str = Field(
        default="https://www.wildberries.ru",
        description="Базовый URL сайта Wildberries.",
    )
    api_search_url: str = Field(
        default="https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search",
        description="URL поискового API Wildberries.",
    )

    # Заголовки для имитации браузера (будут динамически обновляться через fake-useragent)
    api_headers: dict = Field(
        default_factory=lambda: {
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "priority": "u=1, i",
            "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest",
            "x-spa-version": "14.5.7",
            "x-userid": "0",
        },
        description="Заголовки HTTP-запросов к API Wildberries.",
    )

    # Параметры запросов
    request_timeout: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Таймаут HTTP-запросов в секундах.",
    )
    delay_between_requests: float = Field(
        default=0.3,
        ge=0.0,
        le=10.0,
        description="Задержка между последовательными запросами в секундах.",
    )
    page_delay: float = Field(
        default=0.1,
        ge=0.0,
        le=5.0,
        description="Задержка между загрузкой страниц в секундах.",
    )
    max_threads: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Максимальное количество потоков для параллельных запросов.",
    )

    # Параметры API
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Максимальное количество повторных попыток при ошибках.",
    )
    retry_delays: list[float] = Field(
        default_factory=lambda: [1.0, 2.0, 3.0],
        description="Список задержек между повторными попытками в секундах.",
    )
    token_cookie_name: str = Field(
        default="x_wbaas_token",
        description="Имя cookie, содержащего авторизационный токен.",
    )

    # Папки вывода
    output_dir: str = Field(
        default="output",
        description="Директория для сохранения экспортированных файлов.",
    )
    full_catalog_filename: str = Field(
        default="full_catalog.xlsx",
        description="Имя файла полного каталога.",
    )
    filtered_catalog_filename: str = Field(
        default="filtered_catalog.xlsx",
        description="Имя файла отфильтрованного каталога.",
    )
    basic_catalog_filename: str = Field(
        default="basic_catalog.xlsx",
        description="Имя файла базового каталога.",
    )

    # Логирование
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Уровень детализации логов.",
    )
    log_format: str = Field(
        default="[%(asctime)s.%(msecs)03d] %(levelname)-8s %(funcName)20s %(module)s:%(lineno)d - %(message)s",
        description="Формат строк логов.",
    )
    logs_dir: str = Field(
        default="logs",
        description="Директория для хранения лог-файлов.",
    )
    log_format_json: bool = Field(
        default=False,
        description="Использовать JSON-формат для логов (удобно для Docker).",
    )
    log_max_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10 МБ
        ge=1024,
        le=100 * 1024 * 1024,
        description="Максимальный размер лог-файла перед ротацией в байтах.",
    )
    log_backup_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Количество резервных копий лог-файлов.",
    )
    log_separate_error_file: bool = Field(
        default=True,
        description="Сохранять ошибки уровня ERROR и выше в отдельный файл errors.log.",
    )

    # Критерии фильтрации
    min_rating: float = Field(
        default=4.5,
        ge=0.0,
        le=5.0,
        description="Минимальный рейтинг товара для включения в отфильтрованный каталог.",
    )
    max_price: float = Field(
        default=10000.0,
        ge=0.0,
        description="Максимальная цена товара для включения в отфильтрованный каталог.",
    )
    target_country: str = Field(
        default="Россия",
        description="Целевая страна производства товара.",
    )

    # Поисковый запрос по умолчанию
    default_search_query: str = Field(
        default="пальто из натуральной шерсти",
        description="Поисковый запрос по умолчанию.",
    )

    # Параметры поискового API
    search_api_params: dict = Field(
        default_factory=lambda: {
            "ab_testing": ["false", "false"],
            "appType": "1",
            "curr": "rub",
            "dest": "-412733",
            "hide_vflags": "4294967296",
            "inheritFilters": "false",
            "lang": "ru",
            "resultset": "catalog",
            "sort": "popular",
            "spp": "30",
            "suppressSpellcheck": "false",
        },
        description="Параметры запроса к поисковому API.",
    )

    # Параметры парсинга
    limit_per_request: int = Field(
        default=1200,
        ge=1,
        le=10000,
        description="Максимальное количество товаров, получаемых за один запрос.",
    )
    default_base_ranges: list[tuple[int, int]] = Field(
        default_factory=lambda: [
            (0, 5000),
            (5001, 10000),
            (10001, 15000),
            (15001, 25000),
            (25001, 10000000),
        ],
        description="Диапазоны цен для разбивки запросов.",
    )

    # Ротация User-Agent
    user_agent_rotation: bool = Field(
        default=True,
        description="Включить автоматическую ротацию User-Agent.",
    )

    # Прокси
    proxy_pool: list[str] = Field(
        default_factory=list,
        description="Список прокси в формате 'http://user:pass@host:port,http://...'.",
    )

    # Экспоненциальный backoff
    exponential_backoff_base: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Базовый множитель для экспоненциальной задержки.",
    )
    exponential_backoff_max_delay: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Максимальная задержка в секундах при экспоненциальном backoff.",
    )

    @field_validator("retry_delays", mode="before")
    @classmethod
    def parse_retry_delays(cls, v):
        """Парсит строку с задержками в список чисел."""
        if isinstance(v, str):
            try:
                return [float(item.strip()) for item in v.split(",")]
            except ValueError:
                pass
        return v

    @field_validator("search_api_params", mode="before")
    @classmethod
    def parse_search_api_params(cls, v):
        """Парсит JSON-строку в словарь."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass
        return v

    @field_validator("default_base_ranges", mode="before")
    @classmethod
    def parse_default_base_ranges(cls, v):
        """Парсит строку диапазонов в список кортежей."""
        if isinstance(v, str):
            try:
                ranges = []
                for part in v.split(";"):
                    if not part.strip():
                        continue
                    left, right = part.split("-")
                    ranges.append((int(left.strip()), int(right.strip())))
                return ranges
            except (ValueError, AttributeError):
                pass
        return v

    @field_validator("proxy_pool", mode="before")
    @classmethod
    def parse_proxy_pool(cls, v):
        """Парсит строку прокси в список URL."""
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v

    def ensure_output_dir(self) -> Path:
        """Создаёт директорию для вывода, если её нет, и возвращает Path."""
        path = Path(self.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_logs_dir(self) -> Path:
        """Создаёт директорию для логов, если её нет, и возвращает Path."""
        path = Path(self.logs_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Глобальный экземпляр настроек
settings = AppSettings()

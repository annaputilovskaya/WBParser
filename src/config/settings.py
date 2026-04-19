"""Конфигурационные параметры парсера."""
from pathlib import Path
from typing import Final, Literal


class Settings:
    """Настройки приложения."""

    # Базовые URL Wildberries
    BASE_URL: Final[str] = "https://www.wildberries.ru"
    SEARCH_URL: Final[str] = f"{BASE_URL}/catalog"
    BASE_PRODUCT_URL: Final[str] = f"{BASE_URL}/product"

    API_SEARCH_URL: Final[str] = "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search"
    API_PRODUCT_URL: Final[str] = "https://identical-products.wildberries.ru/api/v1/identical"

    # Заголовки для имитации браузера
    API_HEADERS: Final[dict] = {
        "accept": "*/*",
        "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "priority": "u=1, i",
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest",
        "x-spa-version": "14.5.7",
        "x-userid": "0",
    }

    # Параметры запросов
    REQUEST_TIMEOUT: Final[int] = 30
    MAX_CONCURRENT_REQUESTS: Final[int] = 5
    DELAY_BETWEEN_REQUESTS: Final[float] = 1.0  # секунды

    # Параметры API
    MAX_RETRIES: Final[int] = 2
    RETRY_DELAYS: Final[list] = [1, 2]
    CONCURRENT_REQUESTS: Final[int] = 5
    REQUEST_DELAY: Final[float] = 0.5
    TOKEN_COOKIE_NAME: Final[str] = "x_wbaas_token"

    # Папки вывода
    OUTPUT_DIR: Final[str] = "output"
    FULL_CATALOG_FILENAME: Final[str] = "full_catalog.xlsx"
    FILTERED_CATALOG_FILENAME: Final[str] = "filtered_catalog.xlsx"
    BASIC_CATALOG_FILENAME: Final[str] = "basic_catalog.xlsx"

    # Логирование
    LOG_LEVEL: Final[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]] = "INFO"
    LOG_FORMAT: Final[str] = (
        "[%(asctime)s.%(msecs)03d] %(levelname)-8s %(funcName)20s %(module)s:%(lineno)d - %(message)s"
    )
    LOGS_DIR: Final[str] = "logs"

    # Критерии фильтрации
    MIN_RATING: Final[float] = 4.5
    MAX_PRICE: Final[float] = 10000.0
    TARGET_COUNTRY: Final[str] = "Россия"

    # Поисковый запрос по умолчанию
    DEFAULT_SEARCH_QUERY: Final[str] = "пальто из натуральной шерсти"

    @classmethod
    def _ensure_dir(cls, dir_name: str) -> Path:
        """Вспомогательный метод для создания директории."""
        path = Path(dir_name)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def ensure_output_dir(cls) -> Path:
        """Создаёт директорию для вывода, если её нет, и возвращает Path."""
        return cls._ensure_dir(cls.OUTPUT_DIR)

    @classmethod
    def ensure_logs_dir(cls) -> Path:
        """Создаёт директорию для логов, если её нет, и возвращает Path."""
        return cls._ensure_dir(cls.LOGS_DIR)


settings = Settings()

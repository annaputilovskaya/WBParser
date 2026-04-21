"""Конфигурационные параметры парсера."""

from pathlib import Path
from typing import Final, Literal


class Settings:
    """Настройки приложения."""

    # Базовые URL Wildberries
    BASE_URL: Final[str] = "https://www.wildberries.ru"

    API_SEARCH_URL: Final[str] = (
        "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search"
    )

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

    # Параметры запросов (оптимизированы на основе экспериментальных данных)
    REQUEST_TIMEOUT: Final[int] = 10
    DELAY_BETWEEN_REQUESTS: Final[float] = 0.3
    PAGE_DELAY: Final[float] = 0.1
    MAX_THREADS: Final[int] = 30

    # Параметры API
    MAX_RETRIES: Final[int] = 3
    RETRY_DELAYS: Final[list] = [1, 2, 3]
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

    # Параметры поискового API
    SEARCH_API_PARAMS: Final[dict] = {
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
    }

    # Параметры парсинга
    LIMIT_PER_REQUEST: Final[int] = 1200
    DEFAULT_BASE_RANGES: Final[list[tuple[int, int]]] = [
        (0, 5000),
        (5001, 10000),
        (10001, 15000),
        (15001, 25000),
        (25001, 10000000),
    ]

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

    @classmethod
    def validate(cls) -> None:
        """Проверяет корректность настроек перед запуском приложения."""
        # Проверка типов и значений числовых параметров
        if not isinstance(cls.REQUEST_TIMEOUT, int) or cls.REQUEST_TIMEOUT <= 0:
            raise ValueError(f"REQUEST_TIMEOUT должен быть положительным целым числом, получено: {cls.REQUEST_TIMEOUT}")

        if not isinstance(cls.DELAY_BETWEEN_REQUESTS, (int, float)) or cls.DELAY_BETWEEN_REQUESTS < 0:
            raise ValueError(f"DELAY_BETWEEN_REQUESTS должен быть неотрицательным числом, получено: {cls.DELAY_BETWEEN_REQUESTS}")

        if not isinstance(cls.MAX_RETRIES, int) or cls.MAX_RETRIES < 0:
            raise ValueError(f"MAX_RETRIES должен быть неотрицательным целым числом, получено: {cls.MAX_RETRIES}")

        if not isinstance(cls.RETRY_DELAYS, list) or len(cls.RETRY_DELAYS) == 0:
            raise ValueError(f"RETRY_DELAYS должен быть непустым списком, получено: {cls.RETRY_DELAYS}")

        for delay in cls.RETRY_DELAYS:
            if not isinstance(delay, (int, float)) or delay < 0:
                raise ValueError(f"Каждая задержка в RETRY_DELAYS должна быть неотрицательным числом, получено: {delay}")

        # Проверка параметров фильтрации
        if not isinstance(cls.MIN_RATING, (int, float)) or cls.MIN_RATING < 0 or cls.MIN_RATING > 5:
            raise ValueError(f"MIN_RATING должен быть числом от 0 до 5, получено: {cls.MIN_RATING}")

        if not isinstance(cls.MAX_PRICE, (int, float)) or cls.MAX_PRICE < 0:
            raise ValueError(f"MAX_PRICE должен быть неотрицательным числом, получено: {cls.MAX_PRICE}")

        # Проверка строковых параметров
        if not isinstance(cls.TARGET_COUNTRY, str) or not cls.TARGET_COUNTRY.strip():
            raise ValueError(f"TARGET_COUNTRY должен быть непустой строкой, получено: {cls.TARGET_COUNTRY}")

        if not isinstance(cls.DEFAULT_SEARCH_QUERY, str) or not cls.DEFAULT_SEARCH_QUERY.strip():
            raise ValueError(f"DEFAULT_SEARCH_QUERY должен быть непустой строкой, получено: {cls.DEFAULT_SEARCH_QUERY}")

        # Проверка параметров API
        if not isinstance(cls.SEARCH_API_PARAMS, dict):
            raise ValueError(f"SEARCH_API_PARAMS должен быть словарём, получено: {type(cls.SEARCH_API_PARAMS)}")

        if not isinstance(cls.LIMIT_PER_REQUEST, int) or cls.LIMIT_PER_REQUEST <= 0:
            raise ValueError(f"LIMIT_PER_REQUEST должен быть положительным целым числом, получено: {cls.LIMIT_PER_REQUEST}")

        if not isinstance(cls.DEFAULT_BASE_RANGES, list) or len(cls.DEFAULT_BASE_RANGES) == 0:
            raise ValueError(f"DEFAULT_BASE_RANGES должен быть непустым списком, получено: {cls.DEFAULT_BASE_RANGES}")

        for range_tuple in cls.DEFAULT_BASE_RANGES:
            if not isinstance(range_tuple, tuple) or len(range_tuple) != 2:
                raise ValueError(f"Каждый элемент DEFAULT_BASE_RANGES должен быть кортежем из двух чисел, получено: {range_tuple}")
            min_val, max_val = range_tuple
            if not isinstance(min_val, int) or not isinstance(max_val, int) or min_val < 0 or max_val < min_val:
                raise ValueError(f"Диапазон цен должен быть кортежем (min, max) где min <= max, получено: {range_tuple}")

        # Проверка URL
        if not cls.API_SEARCH_URL.startswith("http"):
            raise ValueError(f"API_SEARCH_URL должен быть валидным URL, получено: {cls.API_SEARCH_URL}")

        # Проверка заголовков
        if not isinstance(cls.API_HEADERS, dict):
            raise ValueError(f"API_HEADERS должен быть словарём, получено: {type(cls.API_HEADERS)}")

        # Проверка cookie имени
        if not isinstance(cls.TOKEN_COOKIE_NAME, str) or not cls.TOKEN_COOKIE_NAME.strip():
            raise ValueError(f"TOKEN_COOKIE_NAME должен быть непустой строкой, получено: {cls.TOKEN_COOKIE_NAME}")


settings = Settings()

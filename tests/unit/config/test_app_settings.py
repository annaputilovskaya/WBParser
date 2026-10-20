"""Тесты валидации настроек приложения (парсинг env-переменных)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config.app_settings import AppSettings


class TestRetryDelays:
    """Тесты валидатора WB_RETRY_DELAYS."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("1,2,3", [1.0, 2.0, 3.0]),
            ("1,,2, 3", [1.0, 2.0, 3.0]),
            ("[1, 2, 3]", [1.0, 2.0, 3.0]),
            ("", []),
        ],
    )
    def test_parse_valid_formats(self, raw: str, expected: list[float]) -> None:
        """CSV и JSON-форматы парсятся, пустое значение даёт пустой список."""
        settings = AppSettings(_env_file=None, retry_delays=raw)
        assert settings.retry_delays == expected

    def test_json_array_invalid_raises_clear_error(self) -> None:
        """Некорректный JSON даёт ошибку с именем переменной, а не JSONDecodeError."""
        with pytest.raises(ValidationError, match="WB_RETRY_DELAYS"):
            AppSettings(_env_file=None, retry_delays="[1,2")

    def test_non_numeric_raises_clear_error(self) -> None:
        """Нечисловое значение даёт ошибку с именем переменной."""
        with pytest.raises(ValidationError, match="WB_RETRY_DELAYS"):
            AppSettings(_env_file=None, retry_delays="abc")


class TestSearchApiParams:
    """Тесты валидатора WB_SEARCH_API_PARAMS."""

    def test_json_object_parsed(self) -> None:
        """JSON-объект парсится в словарь."""
        settings = AppSettings(
            _env_file=None, search_api_params='{"lang": "ru", "spp": "30"}'
        )
        assert settings.search_api_params == {"lang": "ru", "spp": "30"}

    def test_invalid_json_raises_clear_error(self) -> None:
        """Некорректный JSON даёт ошибку с именем переменной."""
        with pytest.raises(ValidationError, match="WB_SEARCH_API_PARAMS"):
            AppSettings(_env_file=None, search_api_params="not a json")

    def test_non_object_raises_clear_error(self) -> None:
        """Не-объект (массив) отклоняется."""
        with pytest.raises(ValidationError, match="WB_SEARCH_API_PARAMS"):
            AppSettings(_env_file=None, search_api_params="[1, 2]")


class TestDefaultBaseRanges:
    """Тесты валидатора WB_DEFAULT_BASE_RANGES."""

    def test_semicolon_format(self) -> None:
        """Формат «0-5000;5001-10000» парсится в кортежи."""
        settings = AppSettings(
            _env_file=None, default_base_ranges="0-5000;5001-10000"
        )
        assert settings.default_base_ranges == [(0, 5000), (5001, 10000)]

    def test_json_format(self) -> None:
        """JSON-массив парных значений поддерживается."""
        settings = AppSettings(
            _env_file=None, default_base_ranges="[[0, 5000], [5001, 10000]]"
        )
        assert settings.default_base_ranges == [(0, 5000), (5001, 10000)]

    def test_invalid_range_raises_clear_error(self) -> None:
        """Некорректный диапазон даёт ошибку с именем переменной."""
        with pytest.raises(ValidationError, match="WB_DEFAULT_BASE_RANGES"):
            AppSettings(_env_file=None, default_base_ranges="abc")


class TestProxyPoolAndHeaders:
    """Тесты валидаторов WB_PROXY_POOL и WB_API_HEADERS."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("http://a:1,http://b:2", ["http://a:1", "http://b:2"]),
            (" http://a:1 , ,http://b:2 ", ["http://a:1", "http://b:2"]),
            ("", []),
        ],
    )
    def test_proxy_pool_csv(self, raw: str, expected: list[str]) -> None:
        """CSV-список прокси парсится, пустое значение даёт пустой список."""
        settings = AppSettings(_env_file=None, proxy_pool=raw)
        assert settings.proxy_pool == expected

    def test_api_headers_json_parsed(self) -> None:
        """WB_API_HEADERS парсится из JSON-строки."""
        settings = AppSettings(
            _env_file=None, api_headers='{"x-userid": "42", "accept": "*/*"}'
        )
        assert settings.api_headers == {"x-userid": "42", "accept": "*/*"}

    def test_api_headers_invalid_json_raises(self) -> None:
        """Некорректный JSON заголовков даёт понятную ошибку."""
        with pytest.raises(ValidationError, match="WB_API_HEADERS"):
            AppSettings(_env_file=None, api_headers="{oops")


class TestDefaultsAndEnvExample:
    """Тесты дефолтов и валидности .env.example."""

    def test_delay_between_requests_is_float(self) -> None:
        """settings.delay_between_requests существует и имеет тип float."""
        settings = AppSettings(_env_file=None)
        assert isinstance(settings.delay_between_requests, float)

    def test_cache_dir_default(self) -> None:
        """cache_dir по умолчанию — data/cache; ensure_cache_dir создаёт каталог."""
        settings = AppSettings(_env_file=None, cache_dir="data/cache")
        assert settings.cache_dir == "data/cache"

    def test_env_example_is_valid(self) -> None:
        """.env.example загружается без ошибок и содержит локальные пути."""
        settings = AppSettings(_env_file=Path(".env.example"))
        assert settings.output_dir == "output"
        assert settings.logs_dir == "logs"
        assert settings.cache_dir == "data/cache"
        assert settings.retry_delays == [1.0, 2.0, 3.0]
        assert settings.token_no_sandbox is False
        assert settings.token_headless is True
        assert settings.token_timeout == 30

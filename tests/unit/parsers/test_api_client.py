"""Юнит-тесты для API клиента Wildberries."""

import logging
from unittest.mock import Mock

import pytest
import requests
from _pytest.logging import LogCaptureFixture
from pytest_mock import MockerFixture
from src.config.app_settings import settings
from src.parsers.api_client import IApiClient, WbApiClient
from src.utils.exceptions import TokenFetchError


class TestIApiClient:
    """Тесты интерфейса IApiClient."""

    def test_interface_methods_exist(self) -> None:
        """Проверяет, что интерфейс определяет обязательные методы."""
        assert hasattr(IApiClient, "search_products")
        assert hasattr(IApiClient, "get_product_details")
        with pytest.raises(TypeError):
            IApiClient()


class TestWbApiClient:
    """Тесты для класса WbApiClient."""

    @pytest.fixture
    def mock_token_manager(self, mocker: MockerFixture) -> Mock:
        """Фикстура, возвращающая мок менеджера токенов."""
        token_manager = mocker.Mock()
        token_manager.get_token.return_value = "fake_token"
        return token_manager

    @pytest.fixture
    def api_client(
        self, mocker: MockerFixture, mock_token_manager: Mock
    ) -> WbApiClient:
        """Фикстура, создающая экземпляр WbApiClient с мокнутыми зависимостями."""
        mocker.patch(
            "src.parsers.api_client.TokenManager", return_value=mock_token_manager
        )
        mocker.patch("time.sleep", return_value=None)
        client = WbApiClient()
        client.session = mocker.Mock()
        return client

    @pytest.fixture
    def api_client_with_proxy(
        self, mocker: MockerFixture, mock_token_manager: Mock
    ) -> WbApiClient:
        """Клиент с замоканным пулом прокси."""
        mocker.patch(
            "src.parsers.api_client.TokenManager", return_value=mock_token_manager
        )
        mocker.patch("time.sleep", return_value=None)
        proxy_pool = mocker.Mock()
        proxy_pool.get_next_proxy.return_value = "http://proxy1:1"
        proxy_pool.rotate.return_value = "http://proxy2:2"
        client = WbApiClient(proxy_pool=proxy_pool)
        client.session = mocker.Mock()
        return client

    def test_initialization(self, api_client: WbApiClient) -> None:
        """Проверяет корректность инициализации клиента."""
        assert api_client.token_manager is not None
        assert api_client.session is not None

    @pytest.mark.parametrize(
        "status_code, response_json, expected_result",
        [
            (200, {"products": []}, {"products": []}),
            (200, {"data": {"products": []}}, {"data": {"products": []}}),
            (404, None, None),
            (498, None, None),  # токен истек
            (500, None, None),  # серверная ошибка
        ],
    )
    def test_make_request_various_responses(
        self,
        api_client: WbApiClient,
        mocker: MockerFixture,
        status_code: int,
        response_json: dict | None,
        expected_result: dict | None,
    ) -> None:
        """Проверяет обработку различных HTTP ответов в _make_request."""
        mock_response = mocker.Mock()
        mock_response.status_code = status_code
        if response_json is not None:
            mock_response.json.return_value = response_json
        api_client.session.get.return_value = mock_response

        result = api_client._make_request("https://example.com", {"param": "value"})

        if status_code == 200:
            assert result == response_json
        else:
            assert result is None

    def test_make_request_network_exception(self, api_client: WbApiClient) -> None:
        """Проверяет обработку исключения сети в _make_request."""
        api_client.session.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )
        result = api_client._make_request("https://example.com", {})
        assert result is None

    def test_make_request_json_decode_error(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Проверяет обработку ошибки декодирования JSON в _make_request."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = requests.exceptions.JSONDecodeError(
            "Invalid JSON", "", 0
        )
        api_client.session.get.return_value = mock_response

        result = api_client._make_request("https://example.com", {})
        assert result is None

    def test_make_request_token_expired_and_retry(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Проверяет обновление токена при статусе 498 и повторный запрос."""
        response_498 = mocker.Mock()
        response_498.status_code = 498
        response_200 = mocker.Mock()
        response_200.status_code = 200
        response_200.json.return_value = {"success": True}

        api_client.session.get.side_effect = [response_498, response_200]

        result = api_client._make_request("https://example.com", {})
        assert api_client.token_manager.token is None
        assert result == {"success": True}
        assert api_client.session.get.call_count == 2

    @pytest.mark.parametrize(
        "query, page, price_min, price_max, expected_price_param",
        [
            ("тест", 1, None, None, None),
            ("тест", 2, 1000, 5000, "100000;500000"),
            (None, 1, None, None, None),
        ],
    )
    def test_search_products_params(
        self,
        api_client: WbApiClient,
        mocker: MockerFixture,
        query: str | None,
        page: int,
        price_min: int | None,
        price_max: int | None,
        expected_price_param: str | None,
    ) -> None:
        """Проверяет формирование параметров запроса в search_products."""
        mock_make_request = mocker.patch.object(api_client, "_make_request")
        mock_make_request.return_value = {"products": []}

        result = api_client.search_products(
            query=query, page=page, price_min=price_min, price_max=price_max
        )

        call_args = mock_make_request.call_args
        assert call_args is not None
        called_url, called_params = call_args[0]
        assert called_url == settings.api_search_url
        assert called_params["page"] == page
        if query is not None:
            assert called_params["query"] == query
        if expected_price_param is not None:
            assert called_params["priceU"] == expected_price_param
        else:
            assert "priceU" not in called_params
        assert result == {"products": []}

    def test_search_products_retry_on_few_products(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Проверяет повторный запрос при получении аномально малого количества товаров."""
        mock_make_request = mocker.patch.object(api_client, "_make_request")
        mock_make_request.return_value = {"products": [{"id": 1}]}
        result = api_client.search_products("тест", page=1)
        assert mock_make_request.call_count > 1
        assert result == {"products": [{"id": 1}]}

    def test_search_products_returns_none_after_all_retries(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Проверяет, что search_products возвращает None после исчерпания попыток."""
        mock_make_request = mocker.patch.object(api_client, "_make_request")
        mock_make_request.return_value = None
        result = api_client.search_products("тест", page=1)
        assert result is None
        assert mock_make_request.call_count == settings.max_retries + 1

    def test_get_product_details(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Проверяет запрос детальной информации о товаре."""
        mock_make_request = mocker.patch.object(api_client, "_make_request")
        mock_make_request.return_value = {"description": "Товар"}
        result = api_client.get_product_details(1234567)
        call_args = mock_make_request.call_args
        assert call_args is not None
        called_url, called_params = call_args[0]
        assert "1234567" in called_url
        assert called_params == {}
        assert result == {"description": "Товар"}

    def test_get_product_details_returns_none_on_failure(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Проверяет, что get_product_details возвращает None при ошибке."""
        mock_make_request = mocker.patch.object(api_client, "_make_request")
        mock_make_request.return_value = None
        result = api_client.get_product_details(1234567)
        assert result is None

    def test_make_request_uses_proxy(
        self, api_client_with_proxy: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Прокси из пула передаётся в HTTP-запрос."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        api_client_with_proxy.session.get.return_value = mock_response

        api_client_with_proxy._make_request("https://example.com", {})

        api_client_with_proxy.proxy_pool.get_next_proxy.assert_called_once()
        kwargs = api_client_with_proxy.session.get.call_args.kwargs
        assert kwargs["proxies"] == {
            "http": "http://proxy1:1",
            "https": "http://proxy1:1",
        }

    def test_make_request_rotates_proxy_on_network_error(
        self, api_client_with_proxy: WbApiClient
    ) -> None:
        """При сетевой ошибке прокси ротируется и повторяет запрос."""
        api_client_with_proxy.session.get.side_effect = (
            requests.exceptions.RequestException("network")
        )

        result = api_client_with_proxy._make_request("https://example.com", {})

        assert result is None
        assert api_client_with_proxy.proxy_pool.rotate.call_count == (
            settings.max_retries + 1
        )
        first_kwargs = api_client_with_proxy.session.get.call_args_list[0].kwargs
        assert first_kwargs["proxies"] == {
            "http": "http://proxy1:1",
            "https": "http://proxy1:1",
        }
        last_kwargs = api_client_with_proxy.session.get.call_args.kwargs
        assert last_kwargs["proxies"] == {
            "http": "http://proxy2:2",
            "https": "http://proxy2:2",
        }

    def test_search_products_rotates_user_agent(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """UA обновляется при каждом запросе страницы."""
        mocker.patch.object(api_client, "_update_user_agent_header")
        mocker.patch.object(
            api_client,
            "_make_request",
            return_value={"products": [{"id": 1}, {"id": 2}]},
        )

        api_client.search_products("тест", page=1)

        api_client._update_user_agent_header.assert_called_once()

    def test_search_products_handles_token_fetch_error(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Ошибка получения токена не роняет парсинг: ретраи, затем None."""
        mocker.patch.object(
            api_client, "_make_request", side_effect=TokenFetchError("нет токена")
        )

        result = api_client.search_products("тест", page=1)

        assert result is None
        assert api_client._make_request.call_count == settings.max_retries + 1

    def test_make_request_invalid_url_does_not_log_proxy_secret(
        self,
        api_client_with_proxy: WbApiClient,
        caplog: LogCaptureFixture,
    ) -> None:
        """InvalidURL с паролем не попадает в логи с трейсом/текстом."""
        api_client_with_proxy.session.get.side_effect = requests.exceptions.InvalidURL(
            "Failed to parse: http://user:secret@proxy:8080"
        )

        with caplog.at_level("DEBUG"):
            result = api_client_with_proxy._make_request("https://example.com", {})

        assert result is None
        for rec in caplog.records:
            assert "secret" not in rec.getMessage()
            assert rec.exc_info is None

    def test_search_products_handles_value_error_without_retry(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Неожиданная ошибка не ретраится и не роняет run."""
        mocker.patch.object(
            api_client, "_make_request", side_effect=ValueError("bad data")
        )

        result = api_client.search_products("тест", page=1)

        assert result is None
        assert api_client._make_request.call_count == 1

    def test_search_products_handles_non_dict_response(
        self, api_client: WbApiClient, mocker: MockerFixture
    ) -> None:
        """Неожиданный формат ответа (не словарь) не роняет парсинг."""
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        api_client.session.get.return_value = mock_response

        result = api_client.search_products("тест", page=1)

        assert result is None

    def test_request_failure_logs_single_error_record(
        self,
        api_client_with_proxy: WbApiClient,
        mocker: MockerFixture,
        caplog: LogCaptureFixture,
    ) -> None:
        """Одна ошибка запроса даёт одну запись ERROR (без дубля от _rotate_proxy)."""
        mocker.patch.object(settings, "max_retries", 0)
        api_client_with_proxy.session.get.side_effect = (
            requests.exceptions.RequestException("network down")
        )

        with caplog.at_level(logging.DEBUG):
            result = api_client_with_proxy._make_request("https://example.com", {})

        assert result is None
        errors = [rec for rec in caplog.records if rec.levelno == logging.ERROR]
        assert len(errors) == 1
        assert "Ошибка сети при запросе" in errors[0].getMessage()
        rotations = [
            rec for rec in caplog.records if "ротация прокси" in rec.getMessage()
        ]
        assert rotations
        assert all(rec.levelno == logging.DEBUG for rec in rotations)

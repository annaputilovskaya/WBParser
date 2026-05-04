"""Юнит-тесты для сервиса URL и менеджера корзин."""

import json
import time
from pathlib import Path
from unittest.mock import Mock, mock_open

import pytest
import requests
from pytest_mock import MockerFixture

from src.utils.url_service import BasketManager, UrlService


class TestBasketManager:
    """Тесты для класса BasketManager."""

    @pytest.fixture
    def mock_config_valid(self) -> dict:
        """Фикстура, возвращающая валидную конфигурацию корзин."""
        return {
            "origin": {
                "mediabasket_route_map": [
                    {
                        "hosts": [
                            {
                                "host": "basket-01.wbbasket.ru",
                                "vol_range_from": 0,
                                "vol_range_to": 10,
                            },
                            {
                                "host": "basket-12.wbbasket.ru",
                                "vol_range_from": 11,
                                "vol_range_to": 20,
                            },
                        ]
                    }
                ]
            }
        }

    @pytest.fixture
    def mock_config_empty(self) -> dict:
        """Фикстура, возвращающая пустую конфигурацию."""
        return {}

    @pytest.fixture
    def mock_config_malformed(self) -> dict:
        """Фикстура, возвращающая некорректную структуру."""
        return {"origin": {}}

    @pytest.fixture
    def mock_config_no_hosts(self) -> dict:
        """Фикстура, возвращающая конфигурацию без хостов."""
        return {"origin": {"mediabasket_route_map": [{}]}}

    @pytest.fixture
    def mock_file_path(self, tmp_path: Path) -> Path:
        """Фикстура, возвращающая временный путь к файлу baskets.json."""
        return tmp_path / "baskets.json"

    def test_get_basket_number_with_valid_vol(
        self, mock_config_valid: dict, mocker: MockerFixture
    ) -> None:
        """Проверяет определение номера корзины для vol в диапазоне."""
        mocker.patch.object(
            BasketManager, "_get_config", return_value=mock_config_valid
        )
        assert BasketManager.get_basket_number(5) == "01"
        assert BasketManager.get_basket_number(15) == "12"

    def test_get_basket_number_with_vol_out_of_range(
        self, mock_config_valid: dict, mocker: MockerFixture
    ) -> None:
        """Проверяет возврат корзины по умолчанию при vol вне диапазонов."""
        mocker.patch.object(
            BasketManager, "_get_config", return_value=mock_config_valid
        )
        assert BasketManager.get_basket_number(100) == "01"

    def test_get_basket_number_with_empty_config(
        self, mock_config_empty: dict, mocker: MockerFixture
    ) -> None:
        """Проверяет возврат корзины по умолчанию при пустой конфигурации."""
        mocker.patch.object(
            BasketManager, "_get_config", return_value=mock_config_empty
        )
        assert BasketManager.get_basket_number(5) == "01"

    def test_get_basket_number_with_malformed_config(
        self, mock_config_malformed: dict, mocker: MockerFixture
    ) -> None:
        """Проверяет обработку некорректной структуры конфигурации."""
        mocker.patch.object(
            BasketManager, "_get_config", return_value=mock_config_malformed
        )
        assert BasketManager.get_basket_number(5) == "01"

    def test_get_basket_number_with_no_hosts(
        self, mock_config_no_hosts: dict, mocker: MockerFixture
    ) -> None:
        """Проверяет обработку конфигурации без списка хостов."""
        mocker.patch.object(
            BasketManager, "_get_config", return_value=mock_config_no_hosts
        )
        assert BasketManager.get_basket_number(5) == "01"

    def test_get_basket_number_exception_handling(self, mocker: MockerFixture) -> None:
        """Проверяет обработку исключений внутри метода."""
        mocker.patch.object(
            BasketManager,
            "_get_config",
            side_effect=Exception("Произвольная ошибка"),
        )
        # Метод должен вернуть "01" по умолчанию
        assert BasketManager.get_basket_number(5) == "01"

    def test_get_config_file_exists_and_fresh(
        self, mock_file_path: Path, mocker: MockerFixture
    ) -> None:
        """Проверяет чтение конфигурации из свежего файла."""
        config_data = {"origin": {"mediabasket_route_map": []}}
        mock_file_path.write_text(json.dumps(config_data), encoding="utf-8")
        mocker.patch.object(BasketManager, "FILE_PATH", str(mock_file_path))
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.path.getmtime", return_value=time.time() - 3600)  # 1 час назад
        mock_update = mocker.patch.object(BasketManager, "_update_config")
        result = BasketManager._get_config()
        assert result == config_data
        mock_update.assert_not_called()

    def test_get_config_file_outdated_triggers_update(
        self, mock_file_path: Path, mocker: MockerFixture
    ) -> None:
        """Проверяет обновление конфигурации при устаревшем файле."""
        config_data = {"origin": {"mediabasket_route_map": []}}
        mock_file_path.write_text(json.dumps(config_data), encoding="utf-8")
        mocker.patch.object(BasketManager, "FILE_PATH", str(mock_file_path))
        mocker.patch("os.path.exists", return_value=True)
        # Время модификации больше CACHE_HOURS
        mocker.patch(
            "os.path.getmtime",
            return_value=time.time() - (BasketManager.CACHE_HOURS + 1) * 3600,
        )
        mock_update = mocker.patch.object(BasketManager, "_update_config")
        mocker.patch("builtins.open", mock_open(read_data=json.dumps(config_data)))
        BasketManager._get_config()
        mock_update.assert_called_once()

    def test_get_config_file_not_exists_triggers_update(
        self, mock_file_path: Path, mocker: MockerFixture
    ) -> None:
        """Проверяет обновление конфигурации при отсутствии файла."""
        mocker.patch.object(BasketManager, "FILE_PATH", str(mock_file_path))
        mocker.patch("os.path.exists", return_value=False)
        mock_update = mocker.patch.object(BasketManager, "_update_config")
        # После обновления файл будет создан, но мы мокаем open, чтобы вернуть пустой dict
        mocker.patch("builtins.open", mock_open(read_data=json.dumps({})))
        result = BasketManager._get_config()
        mock_update.assert_called_once()
        assert result == {}

    def test_get_config_file_read_exception_returns_empty_dict(
        self, mock_file_path: Path, mocker: MockerFixture
    ) -> None:
        """Проверяет возврат пустого словаря при ошибке чтения файла."""
        mocker.patch.object(BasketManager, "FILE_PATH", str(mock_file_path))
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.path.getmtime", return_value=time.time() - 3600)
        # Имитируем исключение при открытии файла
        mocker.patch("builtins.open", side_effect=Exception("Ошибка чтения"))
        result = BasketManager._get_config()
        assert result == {}

    def test_update_config_success(self, mocker: MockerFixture) -> None:
        """Проверяет успешное обновление конфигурации с сервера."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"origin": {"mediabasket_route_map": []}}
        mocker.patch("requests.get", return_value=mock_response)
        mock_open_file = mock_open()
        mocker.patch("builtins.open", mock_open_file)
        mocker.patch("json.dump")
        mock_logger = mocker.patch("src.utils.url_service.logger.info")
        BasketManager._update_config()
        requests.get.assert_called_once_with(BasketManager.URL, timeout=10)
        mock_open_file.assert_called_once_with(
            BasketManager.FILE_PATH, "w", encoding="utf-8"
        )
        mock_logger.assert_called_once_with("Конфигурация корзин успешно обновлена")

    def test_update_config_http_error(self, mocker: MockerFixture) -> None:
        """Проверяет обработку HTTP ошибки при обновлении конфигурации."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.HTTPError("404")
        mocker.patch("requests.get", return_value=mock_response)
        mock_logger = mocker.patch("src.utils.url_service.logger.error")
        BasketManager._update_config()
        mock_logger.assert_called_once()
        # Убедимся, что сообщение об ошибке содержит текст
        call_args = mock_logger.call_args[0]
        assert "Ошибка при обновлении конфигурации корзин" in call_args[0]

    def test_update_config_network_exception(self, mocker: MockerFixture) -> None:
        """Проверяет обработку сетевого исключения (например, timeout)."""
        mocker.patch("requests.get", side_effect=requests.Timeout("Таймаут"))
        mock_logger = mocker.patch("src.utils.url_service.logger.error")
        BasketManager._update_config()
        mock_logger.assert_called_once()
        call_args = mock_logger.call_args[0]
        assert "Ошибка при обновлении конфигурации корзин" in call_args[0]


class TestUrlService:
    """Тесты для класса UrlService."""

    @pytest.fixture
    def mock_basket_manager(self, mocker: MockerFixture) -> Mock:
        """Фикстура, мокающая BasketManager.get_basket_number."""
        mock = mocker.patch.object(BasketManager, "get_basket_number")
        mock.return_value = "05"
        return mock

    def test_get_url_params(
        self, mock_basket_manager: Mock
    ) -> None:
        """Проверяет разбивку артикула на vol, part и basket."""
        vol, part, basket = UrlService._get_url_params(1234567)
        assert vol == 12
        assert part == 1234
        assert basket == "05"
        mock_basket_manager.assert_called_once_with(12)

    def test_get_img_url_default_size(
        self, mock_basket_manager: Mock, mocker: MockerFixture
    ) -> None:
        """Проверяет формирование URL изображения с размером по умолчанию."""
        mocker.patch.object(
            UrlService,
            "_get_url_params",
            return_value=(12, 1234, "05"),
        )
        url = UrlService.get_img_url(article=1234567, img_number=3)
        expected = (
            "https://basket-05.wbbasket.ru/" "vol12/part1234/1234567/images/big/3.webp"
        )
        assert url == expected

    def test_get_img_url_custom_size(
        self, mock_basket_manager: Mock, mocker: MockerFixture
    ) -> None:
        """Проверяет формирование URL изображения с указанным размером."""
        mocker.patch.object(
            UrlService,
            "_get_url_params",
            return_value=(12, 1234, "05"),
        )
        url = UrlService.get_img_url(article=1234567, img_number=1, size="small")
        expected = (
            "https://basket-05.wbbasket.ru/"
            "vol12/part1234/1234567/images/small/1.webp"
        )
        assert url == expected

    def test_get_img_url_another_size(
        self, mock_basket_manager: Mock, mocker: MockerFixture
    ) -> None:
        """Проверяет формирование URL изображения с размером 'tm'."""
        mocker.patch.object(
            UrlService,
            "_get_url_params",
            return_value=(12, 1234, "05"),
        )
        url = UrlService.get_img_url(article=1234567, img_number=5, size="tm")
        expected = (
            "https://basket-05.wbbasket.ru/" "vol12/part1234/1234567/images/tm/5.webp"
        )
        assert url == expected

    def test_get_wb_card_url(
        self, mock_basket_manager: Mock, mocker: MockerFixture
    ) -> None:
        """Проверяет формирование URL JSON-карточки товара."""
        mocker.patch.object(
            UrlService,
            "_get_url_params",
            return_value=(12, 1234, "05"),
        )
        url = UrlService.get_wb_card_url(article=1234567)
        expected = (
            "https://basket-05.wbbasket.ru/" "vol12/part1234/1234567/info/ru/card.json"
        )
        assert url == expected

    def test_generate_image_urls_default_size(
        self, mock_basket_manager: Mock, mocker: MockerFixture
    ) -> None:
        """Проверяет генерацию списка URL для нескольких изображений."""
        mocker.patch.object(
            UrlService,
            "_get_url_params",
            return_value=(12, 1234, "05"),
        )
        mock_get_img = mocker.patch.object(UrlService, "get_img_url")
        mock_get_img.side_effect = lambda article, img_number, size="big": (
            f"https://basket-05.wbbasket.ru/vol12/part1234/1234567/images/{size}/{img_number}.webp"
        )
        urls = UrlService.generate_image_urls(article=1234567, count=3)
        assert len(urls) == 3
        assert (
            urls[0]
            == "https://basket-05.wbbasket.ru/vol12/part1234/1234567/images/big/1.webp"
        )
        assert (
            urls[1]
            == "https://basket-05.wbbasket.ru/vol12/part1234/1234567/images/big/2.webp"
        )
        assert (
            urls[2]
            == "https://basket-05.wbbasket.ru/vol12/part1234/1234567/images/big/3.webp"
        )
        assert mock_get_img.call_count == 3
        calls = mock_get_img.call_args_list
        assert calls[0] == ((1234567, 1, "big"),)
        assert calls[1] == ((1234567, 2, "big"),)
        assert calls[2] == ((1234567, 3, "big"),)

    def test_generate_image_urls_custom_size(
        self, mock_basket_manager: Mock, mocker: MockerFixture
    ) -> None:
        """Проверяет генерацию списка URL с указанным размером."""
        mocker.patch.object(
            UrlService,
            "_get_url_params",
            return_value=(12, 1234, "05"),
        )
        mock_get_img = mocker.patch.object(UrlService, "get_img_url")
        mock_get_img.side_effect = lambda article, img_number, size="big": (
            f"https://basket-05.wbbasket.ru/vol12/part1234/1234567/images/{size}/{img_number}.webp"
        )
        urls = UrlService.generate_image_urls(article=1234567, count=2, size="small")
        assert len(urls) == 2
        assert mock_get_img.call_count == 2
        calls = mock_get_img.call_args_list
        assert calls[0] == ((1234567, 1, "small"),)
        assert calls[1] == ((1234567, 2, "small"),)

    def test_generate_image_urls_zero_count(
        self, mock_basket_manager: Mock
    ) -> None:
        """Проверяет генерацию пустого списка при count=0."""
        urls = UrlService.generate_image_urls(article=1234567, count=0)
        assert urls == []

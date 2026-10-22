"""Сервис для формирования URL изображений и карточек Wildberries."""

import contextlib
import json
import logging
import os
import time
from pathlib import Path
from uuid import uuid4

import requests

from src.config.app_settings import settings
from src.utils.exceptions import BasketConfigError

logger = logging.getLogger(__name__)

_reported_basket_error: str | None = None

_UNEXPECTED_ERROR_PREFIX = "unexpected:"


class BasketManager:
    """Менеджер для управления конфигурацией корзин Wildberries.

    Отвечает за получение, кеширование и актуализацию данных о распределении
    артикулов по серверам (баскетам).
    """

    CACHE_FILENAME = "baskets.json"
    URL = "https://cdn.wbbasket.ru/api/v3/upstreams"
    CACHE_HOURS = 24

    @classmethod
    def _cache_path(cls) -> Path:
        """Возвращает путь к файлу кэша корзин.

        Returns:
            Path: Путь settings.cache_dir/baskets.json (каталог создаётся).
        """
        cache_dir = Path(settings.cache_dir)
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / cls.CACHE_FILENAME

    @classmethod
    def get_basket_number(cls, vol: int) -> str:
        """Определяет номер корзины на основе значения vol.

        Повторяющиеся однотипные ошибки не засоряют лог: первое вхождение
        логируется громко (с трассировкой для неожиданных ошибок), последующие
        — только на уровне DEBUG. Неожиданные ошибки ключуются типом исключения,
        поэтому меняющийся текст ошибки не приводит к новым громким записям.

        Args:
            vol (int): Составляющая артикула (article // 100000).

        Returns:
            str: Номер корзины (например, '01', '12'). По умолчанию '01'.
        """
        global _reported_basket_error

        try:
            config = cls._get_config()
            basket = cls._extract_basket(config, vol)
            _reported_basket_error = None
            return basket
        except BasketConfigError as e:
            error_text = str(e)
            if _reported_basket_error != error_text:
                _reported_basket_error = error_text
                logger.warning(
                    "Не удалось определить номер корзины для vol=%s: %s", vol, e
                )
            else:
                logger.debug(
                    "Не удалось определить номер корзины для vol=%s: %s", vol, e
                )
        except Exception as e:
            error_key = f"{_UNEXPECTED_ERROR_PREFIX}{type(e).__name__}"
            if _reported_basket_error != error_key:
                _reported_basket_error = error_key
                logger.error(
                    "Непредвиденная ошибка при определении номера корзины для vol=%s: %s",
                    vol,
                    e,
                    exc_info=True,
                )
            else:
                logger.debug(
                    "Непредвиденная ошибка при определении номера корзины для vol=%s: %s",
                    vol,
                    e,
                )
        return "01"

    @staticmethod
    def _extract_basket(config: dict, vol: int) -> str:
        """Извлекает номер корзины для vol из конфигурации upstreams.

        Args:
            config (dict): Конфигурация upstreams.
            vol (int): Составляющая артикула (article // 100000).

        Returns:
            str: Номер корзины (например, '01', '12'). По умолчанию '01'.

        Raises:
            BasketConfigError: Конфигурация имеет некорректную структуру.
        """
        if not isinstance(config, dict):
            raise BasketConfigError("Конфигурация корзин имеет некорректный формат")

        origin = config.get("origin", {})
        if not isinstance(origin, dict):
            raise BasketConfigError(
                "Поле origin конфигурации корзин имеет неверный тип"
            )

        route_map = origin.get("mediabasket_route_map", [])
        if not route_map:
            return "01"
        if not isinstance(route_map, list):
            raise BasketConfigError(
                "Поле mediabasket_route_map конфигурации корзин имеет неверный тип"
            )

        for route in route_map:
            if not isinstance(route, dict):
                raise BasketConfigError(
                    "Запись mediabasket_route_map конфигурации корзин имеет неверный тип"
                )
            if "hosts" not in route:
                raise BasketConfigError(
                    "Запись mediabasket_route_map конфигурации корзин не содержит hosts"
                )
            hosts = route["hosts"]
            if not isinstance(hosts, list):
                raise BasketConfigError(
                    "Поле hosts конфигурации корзин имеет неверный тип"
                )

            for entry in hosts:
                if not isinstance(entry, dict):
                    raise BasketConfigError(
                        "Запись hosts конфигурации корзин имеет неверный тип"
                    )
                vol_from = entry.get("vol_range_from")
                vol_to = entry.get("vol_range_to")
                host = entry.get("host")
                if not isinstance(vol_from, int) or not isinstance(vol_to, int):
                    raise BasketConfigError(
                        "Границы диапазона vol в конфигурации корзин должны быть целыми"
                    )
                if not isinstance(host, str):
                    raise BasketConfigError(
                        "Поле host конфигурации корзин должно быть строкой"
                    )
                if vol_from <= vol <= vol_to:
                    # Извлекаем '01' из 'basket-01.wbbasket.ru'
                    return host.split(".")[0].split("-")[-1]
        return "01"

    @classmethod
    def _get_config(cls) -> dict:
        """Получает конфигурацию из локального файла или обновляет её по сети.

        Returns:
            dict: Словарь с конфигурацией upstreams.

        Raises:
            BasketConfigError: Конфигурацию не удалось получить или разобрать.
        """
        try:
            path = cls._cache_path()
            if not os.path.exists(path) or (
                time.time() - os.path.getmtime(path) > cls.CACHE_HOURS * 3600
            ):
                cls._update_config()

            with open(path, encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, TypeError, ValueError) as e:
            raise BasketConfigError("Не удалось получить конфигурацию корзин") from e

        if not isinstance(config, dict):
            raise BasketConfigError("Конфигурация корзин имеет некорректный формат")
        return config

    @classmethod
    def _update_config(cls) -> None:
        """Скачивает актуальный JSON с сервера и сохраняет его атомарно."""
        try:
            response = requests.get(cls.URL, timeout=10)
            response.raise_for_status()
            data = response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.warning("Ошибка при обновлении конфигурации корзин: %s", e)
            return

        tmp_path: Path | None = None
        try:
            path = cls._cache_path()
            # Временный файл создаётся рядом с целевым (тот же том) и уникален
            # для каждой записи, чтобы параллельные обновления не конфликтовали.
            tmp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except OSError as e:
            logger.warning("Ошибка записи кэша корзин: %s", e)
            if tmp_path is not None:
                with contextlib.suppress(OSError):
                    tmp_path.unlink(missing_ok=True)
            return
        logger.info("Конфигурация корзин успешно обновлена")


class UrlService:
    """Сервис для построения URL изображений и JSON-карточек товаров Wildberries."""

    @staticmethod
    def _get_url_params(article: int) -> tuple[int, int, str]:
        """Разбивает артикул на технические составляющие для формирования пути.

        Args:
            article (int): Артикул товара.

        Returns:
            tuple[int, int, str]: Кортеж из (vol, part, basket).
        """
        vol = article // 100000
        part = article // 1000
        basket = BasketManager.get_basket_number(vol)
        return vol, part, basket

    @classmethod
    def get_img_url(cls, article: int, img_number: int = 1, size: str = "big") -> str:
        """Формирует прямую ссылку на конкретное изображение товара.

        Args:
            article (int): Артикул товара.
            img_number (int): Порядковый номер фото (начиная с 1).
            size (str): Размер изображения. Доступные варианты: 'big', 'small', 'tm'.
                По умолчанию 'big'.

        Returns:
            str: Полный URL-адрес изображения в формате .webp.
        """
        vol, part, basket = cls._get_url_params(article)
        return (
            f"https://basket-{basket}.wbbasket.ru/"
            f"vol{vol}/part{part}/{article}/images/{size}/{img_number}.webp"
        )

    @classmethod
    def get_wb_card_url(cls, article: int) -> str:
        """Формирует ссылку на JSON-файл с детальной информацией (card.json).

        Args:
            article (int): Артикул товара.

        Returns:
            str: URL-адрес для запроса детальных данных о товаре.
        """
        vol, part, basket = cls._get_url_params(article)
        return (
            f"https://basket-{basket}.wbbasket.ru/"
            f"vol{vol}/part{part}/{article}/info/ru/card.json"
        )

    @classmethod
    def generate_image_urls(
        cls, article: int, count: int, size: str = "big"
    ) -> list[str]:
        """Генерирует список ссылок для всех доступных изображений товара.

        Args:
            article (int): Артикул товара.
            count (int): Общее количество фотографий товара.
            size (str): Размер изображений. По умолчанию 'big'.

        Returns:
            list[str]: Список строковых URL-адресов.
        """
        return [cls.get_img_url(article, i, size) for i in range(1, count + 1)]

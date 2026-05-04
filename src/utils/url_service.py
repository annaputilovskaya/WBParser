"""Сервис для формирования URL изображений и карточек Wildberries."""

import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)


class BasketManager:
    """Менеджер для управления конфигурацией корзин Wildberries.

    Отвечает за получение, кеширование и актуализацию данных о распределении
    артикулов по серверам (баскетам).
    """

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FILE_PATH = os.path.join(BASE_DIR, "baskets.json")
    URL = "https://cdn.wbbasket.ru/api/v3/upstreams"
    CACHE_HOURS = 24

    @classmethod
    def get_basket_number(cls, vol: int) -> str:
        """Определяет номер корзины на основе значения vol.

        Args:
            vol (int): Составляющая артикула (article // 100000).

        Returns:
            str: Номер корзины (например, '01', '12'). По умолчанию '01'.
        """
        try:
            config = cls._get_config()
            # Получаем список хостов из структуры JSON
            route_map = config.get("origin", {}).get("mediabasket_route_map", [])
            if not route_map:
                return "01"

            hosts = route_map[0].get("hosts", [])
            for entry in hosts:
                if entry["vol_range_from"] <= vol <= entry["vol_range_to"]:
                    # Извлекаем '01' из 'basket-01.wbbasket.ru'
                    return entry["host"].split(".")[0].split("-")[-1]
        except (KeyError, IndexError, Exception):
            pass
        return "01"

    @classmethod
    def _get_config(cls) -> dict:
        """Получает конфигурацию из локального файла или обновляет её по сети.

        Returns:
            dict: Словарь с конфигурацией upstreams.
        """
        if not os.path.exists(cls.FILE_PATH) or (
            time.time() - os.path.getmtime(cls.FILE_PATH) > cls.CACHE_HOURS * 3600
        ):
            cls._update_config()

        try:
            with open(cls.FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def _update_config(cls) -> None:
        """Скачивает актуальный JSON с сервера и сохраняет его локально."""
        try:
            response = requests.get(cls.URL, timeout=10)
            response.raise_for_status()
            with open(cls.FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(response.json(), f, ensure_ascii=False, indent=2)
            logger.info("Конфигурация корзин успешно обновлена")
        except Exception as e:
            logger.error("Ошибка при обновлении конфигурации корзин: %s", e)


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

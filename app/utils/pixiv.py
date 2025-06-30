import logging
from typing import Optional, Dict, Any
from pixivpy_async import AppPixivAPI

from app.core.config import settings

logger = logging.getLogger(__name__)


class PixivClient:
    """
    Асинхронный клиент для работы с API Pixiv.
    Использует библиотеку PixivPy-Async.
    """

    def __init__(self, refresh_token: str):
        self._refresh_token = refresh_token
        self.api = AppPixivAPI()

    async def login(self):
        """Выполняет вход в Pixiv. Должна вызываться один раз при старте бота."""
        try:
            await self.api.login(refresh_token=self._refresh_token)
            logger.info("Успешная аутентификация в Pixiv API.")
            return True
        except Exception:
            logger.error("ОШИБКА АУТЕНТИФИКАЦИИ в Pixiv.", exc_info=True)
            logger.error("Убедитесь, что ваш PIXIV_REFRESH_TOKEN в .env файле действителен и не истек.")
            return False

    async def search(self,
                     query: str,
                     search_target: str = 'partial_match_for_tags',
                     period: Optional[str] = None,
                     rating: Optional[str] = 'safe',
                     offset: Optional[int] = None
                     ) -> Optional[Dict[str, Any]]:
        """
        Выполняет поиск с корректной фильтрацией по рейтингу.
        """
        if not self.api.access_token:
            logger.warning("Токен доступа отсутствует, попытка перелогина...")
            if not await self.login():
                return None

        logger.info(
            f"Выполняю поиск: query='{query}', target='{search_target}', rating='{rating}', offset={offset}"
        )

        try:
            # Сначала всегда запрашиваем ВСЕ результаты, так как это самый надежный способ
            json_result = await self.api.search_illust(
                word=query,
                search_target=search_target,
                sort='date_desc',
                duration=period,
                offset=offset,
            )

            if not json_result or not json_result.illusts:
                return None

            if rating == 'safe':
                logger.debug("Фильтрую результаты для SFW (x_restrict == 0)")
                json_result.illusts = [
                    illust for illust in json_result.illusts if illust.x_restrict == 0
                ]
            elif rating == 'r18':
                logger.debug("Фильтрую результаты для R-18 (x_restrict > 0)")
                json_result.illusts = [
                    illust for illust in json_result.illusts if illust.x_restrict > 0
                ]

            return json_result

        except Exception:
            logger.warning("Ошибка при поиске в Pixiv. Попытка перелогина...", exc_info=True)
            if await self.login():
                logger.info("Перелогин успешен. Повторный поиск...")
                return await self.search(query, search_target, period, rating, offset)
            return None

    def format_illust(self, illust: Dict[str, Any]) -> Dict[str, Any]:
        """Приводит данные об иллюстрации к единому формату для нашего бота."""
        if illust.page_count > 1:
            image_url = illust.meta_pages[0].image_urls.large
            all_images = [p.image_urls.original for p in illust.meta_pages]
        else:
            image_url = illust.meta_single_page.original_image_url
            all_images = [image_url]

        return {
            'id': illust.id,
            'title': illust.title,
            'author': illust.user.name,
            'url': f"https://www.pixiv.net/artworks/{illust.id}",
            'tags': [tag.name for tag in illust.tags],
            'create_date': illust.create_date, # <--- ДОБАВЛЕНА ЭТА СТРОКА
            'image_url': image_url,
            'all_image_urls': all_images,
            'is_r18': illust.x_restrict > 0
        }


# Создаем единый экземпляр клиента для всего бота
pixiv_client = PixivClient(settings.pixiv_refresh_token)

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware для передачи сессии SQLAlchemy в хендлеры.
    """
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Создаем сессию из пула и передаем ее в данные события
        async with self.session_pool() as session:
            data['session'] = session
            # Вызываем следующий обработчик в цепочке, передавая ему обновленные данные
            return await handler(event, data)
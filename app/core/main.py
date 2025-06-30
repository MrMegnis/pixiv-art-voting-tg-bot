import asyncio
import logging
from aiogram import Bot, Dispatcher
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

from .config import settings
from app.database.engine import create_db_and_tables, async_session_factory
from app.database.middleware import DbSessionMiddleware
from app.handlers import common, authorization, user_content, evaluation
from app.handlers.debug import debug_router
from app.utils.pixiv import pixiv_client

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


async def on_startup(bot: Bot):
    """Выполняется при старте бота."""
    print("Инициализация базы данных...")
    await create_db_and_tables()
    print("Аутентификация в Pixiv...")
    await pixiv_client.login()

    # Установка команд меню
    commands = [
        BotCommand(command="/start", description="🚀 Запуск / Перезапуск бота")
    ]
    await bot.set_my_commands(commands)
    print("Бот запущен и готов к работе!")


async def main():
    bot = Bot(token=settings.bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.update.outer_middleware(DbSessionMiddleware(session_pool=async_session_factory))

    # Регистрируем роутеры
    dp.include_router(common.router)
    dp.include_router(authorization.router)
    dp.include_router(user_content.router)
    dp.include_router(evaluation.router)

    dp.include_router(debug_router)

    # Регистрируем хук на запуск
    dp.startup.register(on_startup)

    # Запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")

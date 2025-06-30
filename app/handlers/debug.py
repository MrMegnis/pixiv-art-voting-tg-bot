import logging
from aiogram import Router
from aiogram.types import CallbackQuery

# Этот роутер будет нашей "ловушкой"
debug_router = Router()

@debug_router.callback_query()
async def catch_all_unhandled_callbacks(callback: CallbackQuery):
    """
    Этот хендлер ловит ЛЮБЫЕ нажатия на кнопки, которые не были
    обработаны другими хендлерами.
    """
    # Выводим диагностическую информацию в консоль
    logging.info("\n--- DEBUG: НЕОБРАБОТАННЫЙ КОЛБЭК ---")
    logging.info(f"От пользователя: {callback.from_user.id}")
    logging.info(f"Данные колбэка (callback.data): <{callback.data}>")
    logging.info("-------------------------------------\n")

    # Отвечаем пользователю, чтобы он видел, что что-то произошло
    await callback.answer(
        "Этот колбэк был пойман DEBUG-обработчиком, но не был обработан по назначению.",
        show_alert=True
    )
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import requests as rq
from app.keyboards import inline as ikb
from app.states.user_states import AuthStates

router = Router()

@router.callback_query(F.data == "authorize")
async def start_authorization(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите пароль администратора:")
    await state.set_state(AuthStates.waiting_for_password)
    await callback.answer()

@router.message(AuthStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == settings.admin_password:
        user = await rq.authorize_user(session, message.from_user.id)
        await message.answer(
            "Вы успешно авторизованы! Вам доступны расширенные команды.",
            reply_markup=ikb.get_main_menu(is_authorized=True)
        )
    else:
        await message.answer(
            "Неверный пароль. Попробуйте снова или вернитесь в главное меню.",
            reply_markup=ikb.get_main_menu(is_authorized=False)
        )
    await state.clear()
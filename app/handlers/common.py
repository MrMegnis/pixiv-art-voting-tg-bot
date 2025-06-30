from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import requests as rq
from app.keyboards import inline as ikb
from app.keyboards.callback_data import Action

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user = await rq.get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(
        f"Добро пожаловать, {message.from_user.first_name}!",
        reply_markup=ikb.get_main_menu(user.is_authorized)
    )


@router.callback_query(Action.filter(F.name == "cancel_fsm"))
async def cancel_fsm_handler(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.answer("Действие отменено")
    await state.clear()
    await callback.message.delete()

    user = await rq.get_or_create_user(session, callback.from_user.id)
    await callback.message.answer("Главное меню:", reply_markup=ikb.get_main_menu(user.is_authorized))

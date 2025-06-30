# app/handlers/user_content.py
import os
import json
import csv
import io
from typing import Union, List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import requests as rq
from app.database.models import Rating
from app.keyboards import inline as ikb
from app.keyboards.callback_data import Action
from app.states.user_states import UserContentStates, ExportStates
from app.database.engine import DATA_DIR

router = Router()


async def is_authorized_filter(event: Union[Message, CallbackQuery], session: AsyncSession):
    """
    Проверяет, авторизован ли пользователь.
    Работает и для сообщений, и для колбэков.
    """
    user = await rq.get_or_create_user(session, event.from_user.id)
    return user.is_authorized


# Применяем фильтр ко всем хендлерам в этом роутере
router.message.filter(is_authorized_filter)
router.callback_query.filter(is_authorized_filter)


# --- Вспомогательная функция для генерации CSV ---
async def generate_ratings_csv(ratings: List[Rating], filename: str) -> BufferedInputFile:
    """Генерирует CSV файл из списка оценок."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Заголовки CSV
    writer.writerow([
        'user_id', 'username', 'artwork_id', 'title', 'author',
        'artwork_url', 'user_score', 'source_name', 'rated_at'
    ])

    for rating in ratings:
        writer.writerow([
            rating.user.user_id,
            rating.user.username,
            rating.artwork.pixiv_id,  # Используем pixiv_id для идентификации
            rating.artwork.title,
            rating.artwork.author,
            rating.artwork.url,
            rating.score,
            rating.source.name if rating.source else "Удаленный источник",
            rating.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    output.seek(0)
    return BufferedInputFile(output.getvalue().encode('utf-8'), filename=filename)

# --- Upload ---
@router.callback_query(F.data == "upload_file")
async def start_upload(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserContentStates.waiting_for_file)
    await callback.message.edit_text(
        "Пожалуйста, отправьте мне .json файл с артами.",
        reply_markup=ikb.get_cancel_fsm_keyboard()
    )
    await callback.answer()  # Отвечаем на колбэк, чтобы "часики" на кнопке пропали


@router.message(UserContentStates.waiting_for_file, F.document)
async def process_upload(message: Message, state: FSMContext, session: AsyncSession):
    document = message.document
    if not document.file_name.endswith('.json'):
        await message.answer("Неверный формат. Пожалуйста, отправьте .json файл.")
        return

    filepath = os.path.join(DATA_DIR, document.file_name)
    await message.bot.download(document, destination=filepath)

    await rq.add_file_source(session, document.file_name, filepath, message.from_user.id)
    await message.answer(f"Файл '{document.file_name}' успешно загружен и готов к оценке.")
    await state.clear()


# --- Delete ---
@router.callback_query(F.data == "delete_file")
async def select_file_to_delete(callback: CallbackQuery, session: AsyncSession):
    user_files = await rq.get_user_file_sources(session, callback.from_user.id)
    if not user_files:
        await callback.answer("Вы еще не загрузили ни одного файла.", show_alert=True)
        return

    await callback.message.edit_text(
        "Выберите файл для удаления:",
        reply_markup=await ikb.get_files_to_delete(user_files)
    )


@router.callback_query(Action.filter(F.name == "delete_source"))
async def confirm_delete(callback: CallbackQuery, callback_data: Action, session: AsyncSession):
    source = await rq.get_source_by_id(session, callback_data.source_id)
    if not source or source.owner_id != callback.from_user.id:
        await callback.answer("Файл не найден или у вас нет прав на его удаление.", show_alert=True)
        return

    # Удаляем файл с диска
    filepath = source.details.get('path')
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError as e:
            print(f"Ошибка удаления файла {filepath}: {e}")

    # Удаляем запись из БД
    await rq.delete_source_by_owner(session, callback_data.source_id, callback.from_user.id)
    await callback.message.edit_text(f"Файл '{source.name}' был успешно удален.")


# --- My Stuff ---
@router.callback_query(F.data == "my_stuff")
async def my_stuff_handler(callback: CallbackQuery, session: AsyncSession):
    files = await rq.get_user_file_sources(session, callback.from_user.id)
    if not files:
        await callback.answer("У вас пока нет загруженных файлов.", show_alert=True)
        return

    response_text = "Ваши загруженные файлы:\n\n"
    for file in files:
        response_text += f"📁 {file.name}\n"

    await callback.message.edit_text(response_text)
    await callback.answer()


# --- Export ---
# 1. Главный обработчик, который показывает меню выбора
@router.callback_query(F.data == "export_data")
async def export_data_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите тип экспорта:",
        reply_markup=ikb.get_export_options_keyboard()
    )
    await callback.answer()


# 2. Экспорт своих оценок
@router.callback_query(F.data == "export_mine")
async def export_mine_handler(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("Начинаю экспорт ваших оценок...")
    ratings = await rq.get_user_ratings_for_export(session, callback.from_user.id)

    if not ratings:
        await callback.message.answer("У вас пока нет оценок для экспорта.")
        return

    csv_file = await generate_ratings_csv(ratings, f'export_my_{callback.from_user.id}.csv')
    await callback.message.answer_document(csv_file)
    await callback.message.delete()  # Удаляем меню


# 3. Экспорт всех оценок
@router.callback_query(F.data == "export_all")
async def export_all_handler(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("Начинаю экспорт ВСЕХ оценок...")
    ratings = await rq.get_all_ratings_for_export(session)

    if not ratings:
        await callback.message.answer("В базе данных еще нет ни одной оценки.")
        return

    csv_file = await generate_ratings_csv(ratings, 'export_all_users.csv')
    await callback.message.answer_document(csv_file)
    await callback.message.delete()


# 4. Диалог для экспорта по ID
@router.callback_query(F.data == "export_specific_user")
async def export_specific_user_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ExportStates.waiting_for_user_id)
    await callback.message.edit_text(
        "Пожалуйста, введите Telegram ID пользователя, оценки которого вы хотите экспортировать.",
        reply_markup=ikb.get_cancel_fsm_keyboard()
    )
    await callback.answer()


@router.message(ExportStates.waiting_for_user_id)
async def export_specific_user_process(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text.isdigit():
        await message.answer("Ошибка. Telegram ID должен быть числом. Попробуйте еще раз.")
        return

    user_id = int(message.text)
    await state.clear()

    await message.answer(f"Начинаю экспорт оценок пользователя {user_id}...")
    ratings = await rq.get_user_ratings_for_export(session, user_id)

    if not ratings:
        await message.answer(f"Не найдено оценок для пользователя с ID {user_id}.")
        return

    csv_file = await generate_ratings_csv(ratings, f'export_user_{user_id}.csv')
    await message.answer_document(csv_file)

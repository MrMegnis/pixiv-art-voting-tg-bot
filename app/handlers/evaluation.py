import json
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import requests as rq
from app.keyboards import inline as ikb
from app.keyboards.callback_data import SourceSelect, ArtworkRate, Action, SearchParam, SkipAction
from app.states.user_states import PixivSearchStates
from app.utils.pixiv import pixiv_client

logger = logging.getLogger(__name__)

router = Router()


# --- Общая функция для отправки следующего арта на оценку ---
async def send_next_art_for_rating(message: Message, session: AsyncSession, source_id: int, user_id: int):
    source = await rq.get_source_by_id(session, source_id)
    if not source:
        await message.answer("Источник не найден.")
        return

    progress = await rq.get_user_progress(session, user_id, source_id)
    start_post_index = progress.last_post_index if progress else 0
    start_image_index = progress.last_image_index if progress else 0

    arts_to_check = []
    api_offset = 0
    local_start_index = 0

    if source.source_type == 'file':
        try:
            with open(source.details['path'], 'r', encoding='utf-8') as f:
                raw_json = json.load(f)
                arts_to_check = raw_json.get('illusts', raw_json)
            local_start_index = start_post_index
        except (FileNotFoundError, json.JSONDecodeError):
            await message.answer("Ошибка чтения файла с артами.")
            return

    elif source.source_type == 'query':
        query_params = source.details
        # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Правильно вычисляем страницу и смещение ---
        # API отдает страницы по 30 постов.
        page_size = 30
        # Вычисляем, какой offset нам нужно запросить у API
        api_offset = (start_post_index // page_size) * page_size
        # Вычисляем, с какого поста на этой странице нам нужно начать
        local_start_index = start_post_index % page_size
        # -----------------------------------------------------------------

        pixiv_response = await pixiv_client.search(
            query=query_params['query'], search_target=query_params['target'],
            period=query_params['period'], rating=query_params['rating'],
            offset=api_offset
        )
        if pixiv_response and pixiv_response.illusts:
            arts_to_check = pixiv_response.illusts
        else:
            await message.answer(f"По вашему запросу '{source.name}' больше ничего не найдено.")
            return

    # Основной цикл по постам на текущей странице/в файле
    for item_idx, art_data_raw in enumerate(arts_to_check):
        if item_idx < local_start_index:
            continue

        # Глобальный индекс поста (для кнопок и сохранения прогресса)
        post_idx_global = api_offset + item_idx

        formatted_art = pixiv_client.format_illust(art_data_raw)
        image_urls = formatted_art.get('all_image_urls', [])

        # Вложенный цикл по картинкам внутри поста
        for img_idx, image_url in enumerate(image_urls):
            # Пропускаем уже просмотренные картинки в первом посте
            if item_idx == local_start_index and img_idx < start_image_index:
                continue

            artwork_obj = await rq.get_or_create_artwork(session, formatted_art, img_idx)
            is_rated = await rq.check_user_rating_for_artwork(session, user_id, artwork_obj.id)

            if not is_rated:
                # Сохраняем прогресс на ТЕКУЩИЙ арт перед отправкой
                await rq.update_user_progress(session, user_id, source_id, post_idx_global, img_idx)

                # Формируем подпись и отправляем
                create_date_str = formatted_art['create_date'].split('T')[0]
                tags_str = ", ".join([f"#{tag}" for tag in formatted_art.get('tags', [])])
                caption = (
                    f"<b>{artwork_obj.title}</b> (Изображение {img_idx + 1}/{len(image_urls)})\n"
                    f"Автор: {artwork_obj.author} | Дата: {create_date_str}\n"
                    f"<a href='{artwork_obj.url}'>Ссылка на пост Pixiv</a>\n\n"
                    f"<i>Теги: {tags_str}</i>"
                )

                try:
                    await message.answer_photo(
                        photo=image_url, caption=caption, parse_mode='HTML',
                        reply_markup=ikb.get_rating_keyboard(source_id, artwork_obj.id, post_idx_global)
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить арт {artwork_obj.id}: {e}", exc_info=True)
                    await message.answer(caption, parse_mode='HTML',
                                         reply_markup=ikb.get_rating_keyboard(source_id, artwork_obj.id, post_idx_global))
                return

    # Если мы дошли сюда, значит, все арты на странице/в файле обработаны.
    if source.source_type == 'query' and arts_to_check:
        logger.debug(f"Закончилась страница для запроса '{source.name}'. Пытаюсь загрузить следующую.")
        # Устанавливаем прогресс на начало следующей страницы
        next_page_start_index = api_offset + len(arts_to_check)
        await rq.update_user_progress(session, user_id, source_id, next_page_start_index, 0)
        # Рекурсивно вызываем себя же, чтобы сразу показать арт со следующей страницы
        await send_next_art_for_rating(message, session, source_id, user_id)
        return

    await message.answer(f"🎉 Вы оценили все доступные арты в источнике '{source.name}'!")


# --- Обработчики для оценки из файла ---
@router.callback_query(F.data == "evaluate_from_file")
async def select_file_to_evaluate(callback: CallbackQuery, session: AsyncSession):
    files = await rq.get_all_file_sources(session)
    if not files:
        await callback.answer("Нет доступных файлов для оценки. Администратор должен их загрузить.", show_alert=True)
        return

    # Собираем прогресс пользователя по файлам
    user_progress = {}
    for file_source in files:
        progress = await rq.get_user_progress(session, callback.from_user.id, file_source.source_id)
        if progress:
            user_progress[file_source.source_id] = progress

    await callback.message.edit_text(
        "Выберите файл для начала или продолжения оценки:",
        reply_markup=await ikb.get_files_to_evaluate(files, user_progress)
    )


# --- FSM для оценки по запросу Pixiv ---
@router.callback_query(F.data == "evaluate_from_query")
async def select_or_create_pixiv_query(callback: CallbackQuery, session: AsyncSession):
    user_queries = await rq.get_user_query_sources(session, callback.from_user.id)

    # Готовим подробный текст для сообщения
    if user_queries:
        message_text = "Выберите существующий запрос или создайте новый:\n"

        # Словари для перевода технических названий в человекочитаемые
        target_map = {
            'partial_match_for_tags': 'Теги (частичное совпадение)',
            'exact_match_for_tags': 'Теги (полное совпадение)',
            'title_and_caption': 'Заголовок и описание'
        }
        rating_map = {
            'safe': 'Только SFW',
            'r18': 'Только R-18',
            'all': 'Любой рейтинг'
        }
        period_map = {
            'day': 'За последний день',
            'week': 'За последнюю неделю',
            'month': 'За последний месяц',
        }

        # Формируем нумерованный список с полным описанием каждого запроса
        for i, query in enumerate(user_queries, 1):
            details = query.details
            query_text = details.get('query', 'N/A')
            target_text = target_map.get(details.get('target'), 'N/A')
            rating_text = rating_map.get(details.get('rating'), 'N/A')
            period_text = period_map.get(details.get('period'), 'За всё время')

            message_text += (
                f"\n<b>{i}. Запрос:</b> <code>{query_text}</code>\n"
                f"   - <b>Где искать:</b> {target_text}\n"
                f"   - <b>Рейтинг:</b> {rating_text}\n"
                f"   - <b>Период:</b> {period_text}\n"
            )
    else:
        message_text = "У вас пока нет сохраненных запросов. Создайте новый:"

    await callback.message.edit_text(
        text=message_text,
        # Клавиатура будет сгенерирована новой функцией
        reply_markup=await ikb.get_queries_menu(user_queries),
        # Включаем HTML-разметку для жирного шрифта и моноширинного текста
        parse_mode='HTML',
        disable_web_page_preview=True
    )


@router.callback_query(F.data == "create_new_query")
async def start_pixiv_query_fsm(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PixivSearchStates.waiting_for_keywords)
    await callback.message.edit_text(
        "Введите ключевые слова для поиска.\n\n"
        "<b>Совет:</b> Вы можете использовать операторы:\n"
        "• `word1 word2` - для поиска артов с обоими тегами (И)\n"
        "• `word1 OR word2` - для поиска с одним из тегов (ИЛИ)\n"
        "• `-word3` - для исключения тега\n"
        "• `(word1 OR word2) -word3` - для сложных комбинаций",
        parse_mode='HTML',
        reply_markup=ikb.get_cancel_fsm_keyboard()
    )


@router.message(PixivSearchStates.waiting_for_keywords)
async def process_keywords(message: Message, state: FSMContext):
    await state.update_data(keywords=message.text)
    await state.set_state(PixivSearchStates.waiting_for_target)
    await message.answer("Отлично. Теперь выберите, где искать:", reply_markup=ikb.get_search_target_keyboard())


@router.callback_query(PixivSearchStates.waiting_for_target, SearchParam.filter(F.param == 'target'))
async def process_target(callback: CallbackQuery, callback_data: SearchParam, state: FSMContext):
    await state.update_data(target=callback_data.value)
    await state.set_state(PixivSearchStates.waiting_for_rating)
    await callback.message.edit_text("Понял. Какой возрастной рейтинг вас интересует?",
                                     reply_markup=ikb.get_search_rating_keyboard())


@router.callback_query(PixivSearchStates.waiting_for_rating, SearchParam.filter(F.param == 'rating'))
async def process_rating_filter(callback: CallbackQuery, callback_data: SearchParam, state: FSMContext):
    await state.update_data(rating=callback_data.value)
    await state.set_state(PixivSearchStates.waiting_for_period)
    await callback.message.edit_text("Принято. За какой период искать?", reply_markup=ikb.get_search_period_keyboard())


@router.callback_query(PixivSearchStates.waiting_for_period, SearchParam.filter(F.param == 'period'))
async def process_period_and_finish(callback: CallbackQuery, callback_data: SearchParam, state: FSMContext,
                                    session: AsyncSession):
    await callback.message.edit_text("Собираю все параметры и создаю запрос...")
    await state.update_data(period=callback_data.value)

    data = await state.get_data()
    await state.clear()

    # Сохраняем новый источник в БД
    query_details = {
        'query': data['keywords'],
        'target': data['target'],
        'rating': data['rating'],
        'period': data['period'] if data['period'] != 'all' else None,
    }

    source_name = f"Запрос: {data['keywords'][:30]}..."
    new_source = await rq.add_query_source(session, source_name, query_details, callback.from_user.id)

    await callback.message.edit_text(
        f"Новый запрос '{source_name}' успешно создан! Начинаю оценку...",
        reply_markup=None
    )
    # Запускаем оценку по новосозданному источнику
    await send_next_art_for_rating(callback.message, session, new_source.source_id, callback.from_user.id)


# --- Общие обработчики для процесса оценки ---
@router.callback_query(SourceSelect.filter())
async def start_evaluation(callback: CallbackQuery, callback_data: SourceSelect, session: AsyncSession):
    await callback.message.delete()
    await send_next_art_for_rating(callback.message, session, callback_data.source_id, callback.from_user.id)

async def advance_and_send_next(callback: CallbackQuery, session: AsyncSession, source_id: int):
    """Вспомогательная функция для перехода к следующему арту."""
    progress = await rq.get_user_progress(session, callback.from_user.id, source_id)
    if not progress:
        return

    # Рассчитываем следующий шаг
    source = await rq.get_source_by_id(session, source_id)
    if source.source_type == 'file':
        # Просто переходим к следующей картинке, логика в send_next_art_for_rating найдет ее
        await rq.update_user_progress(session, callback.from_user.id, source_id, progress.last_post_index, progress.last_image_index + 1)
    elif source.source_type == 'query':
        # Для запроса нужно проверить, не вышли ли мы за пределы страницы
        # Это сложная логика, пока просто увеличим индекс картинки
        await rq.update_user_progress(session, callback.from_user.id, source_id, progress.last_post_index, progress.last_image_index + 1)

    await callback.message.delete()
    await send_next_art_for_rating(callback.message, session, source_id, callback.from_user.id)


@router.callback_query(ArtworkRate.filter())
async def process_artwork_rating(callback: CallbackQuery, callback_data: ArtworkRate, session: AsyncSession):
    # 1. Сохраняем оценку
    await rq.add_rating(
        session, user_id=callback.from_user.id, artwork_id=callback_data.artwork_id,
        source_id=callback_data.source_id, score=callback_data.score
    )
    # 2. Удаляем старое сообщение и просим показать следующий арт
    await callback.message.delete()
    await send_next_art_for_rating(callback.message, session, callback_data.source_id, callback.from_user.id)


@router.callback_query(SkipAction.filter(F.action == 'image'))
async def skip_image_handler(callback: CallbackQuery, callback_data: SkipAction, session: AsyncSession):
    await callback.answer("Картинка пропущена")

    progress = await rq.get_user_progress(session, callback.from_user.id, callback_data.source_id)
    if progress:
        await rq.update_user_progress(session, callback.from_user.id, callback_data.source_id, progress.last_post_index,
                                      progress.last_image_index + 1)

    await callback.message.delete()
    await send_next_art_for_rating(callback.message, session, callback_data.source_id, callback.from_user.id)


@router.callback_query(SkipAction.filter(F.action == 'post'))
async def skip_post_handler(callback: CallbackQuery, callback_data: SkipAction, session: AsyncSession):
    await callback.answer("Пост пропущен")

    # Устанавливаем прогресс на начало СЛЕДУЮЩЕГО поста
    await rq.update_user_progress(
        session,
        user_id=callback.from_user.id,
        source_id=callback_data.source_id,
        post_index=callback_data.post_idx + 1,  # Переходим к следующему посту
        image_index=0  # Начинаем с первой картинки
    )

    await callback.message.delete()
    await send_next_art_for_rating(callback.message, session, callback_data.source_id, callback.from_user.id)

@router.callback_query(Action.filter(F.name == "stop_eval"))
async def stop_evaluation(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("Оценка прервана")

    user = await rq.get_or_create_user(session, callback.from_user.id)
    await callback.message.delete()
    await callback.message.answer("Вы можете вернуться к оценке позже.",
                                  reply_markup=ikb.get_main_menu(user.is_authorized))

# ЗАГЛУШКА для поиска по запросу
# @router.callback_query(F.data == "evaluate_from_query")
# async def evaluate_from_query_stub(callback: CallbackQuery):
#     await callback.answer("Функционал оценки по запросу Pixiv находится в разработке.", show_alert=True)

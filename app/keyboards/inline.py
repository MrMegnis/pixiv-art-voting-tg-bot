# app/keyboards/inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .callback_data import SourceSelect, ArtworkRate, Action, SearchParam, SkipAction


def get_main_menu(is_authorized: bool = False):
    buttons = [
        [InlineKeyboardButton(text="🎨 Оценить из файла", callback_data="evaluate_from_file")],
        [InlineKeyboardButton(text="🔍 Оценить по запросу (TBD)", callback_data="evaluate_from_query")],
    ]
    if is_authorized:
        buttons.extend([
            [InlineKeyboardButton(text="📥 Загрузить файл", callback_data="upload_file")],
            [InlineKeyboardButton(text="📂 Мои данные", callback_data="my_stuff")],
            [InlineKeyboardButton(text="🗑️ Удалить файл", callback_data="delete_file")],
            [InlineKeyboardButton(text="📊 Экспорт оценок", callback_data="export_data")],
        ])
    else:
        buttons.append([InlineKeyboardButton(text="🔑 Авторизация", callback_data="authorize")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_files_to_evaluate(files: list, user_progress: dict):
    buttons = []
    for file_source in files:
        # Помечаем файлы, которые пользователь уже начал оценивать
        marker = "🔄 " if file_source.source_id in user_progress else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{marker}{file_source.name}",
                callback_data=SourceSelect(source_id=file_source.source_id).pack()
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_rating_keyboard(source_id: int, artwork_id: int, post_idx: int):
    """
    Создает клавиатуру для оценки, включая кнопки пропуска.
    """
    buttons = [
        [
            InlineKeyboardButton(text=str(i), callback_data=ArtworkRate(source_id=source_id, artwork_id=artwork_id, score=i).pack())
            for i in range(1, 6)
        ],
        [
            InlineKeyboardButton(text=str(i), callback_data=ArtworkRate(source_id=source_id, artwork_id=artwork_id, score=i).pack())
            for i in range(6, 11)
        ],
        [
            InlineKeyboardButton(
                text="⏭️ Пропустить картинку",
                callback_data=SkipAction(action='image', source_id=source_id, post_idx=post_idx).pack()
            ),
            InlineKeyboardButton(
                text="⏩ Пропустить пост",
                callback_data=SkipAction(action='post', source_id=source_id, post_idx=post_idx).pack()
            )
        ],
        [
            InlineKeyboardButton(text="🚫 Прекратить оценку", callback_data=Action(name="stop_eval").pack())
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_files_to_delete(files: list):
    buttons = []
    for file_source in files:
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑️ {file_source.name}",
                callback_data=Action(name="delete_source", source_id=file_source.source_id).pack()
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_fsm_keyboard():
    """Клавиатура для отмены текущего состояния (диалога)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=Action(name="cancel_fsm").pack())]
    ])


def get_search_target_keyboard():
    buttons = [
        [InlineKeyboardButton(
            text="Теги (частичное совпадение)",
            # Было: 'tags_partial', Стало: 'partial_match_for_tags'
            callback_data=SearchParam(param='target', value='partial_match_for_tags').pack()
        )],
        [InlineKeyboardButton(
            text="Теги (полное совпадение)",
            # Было: 'tags_exact', Стало: 'exact_match_for_tags'
            callback_data=SearchParam(param='target', value='exact_match_for_tags').pack()
        )],
        [InlineKeyboardButton(
            text="Заголовок и описание",
            # Это значение было правильным, но для единообразия оставляем.
            callback_data=SearchParam(param='target', value='title_and_caption').pack()
        )],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=Action(name="cancel_fsm").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_search_rating_keyboard():
    buttons = [
        [InlineKeyboardButton(text="✅ Только безопасный контент (SFW)",
                              callback_data=SearchParam(param='rating', value='safe').pack())],
        [InlineKeyboardButton(text="🔞 Только для взрослых (R-18)",
                              callback_data=SearchParam(param='rating', value='r18').pack())],
        [InlineKeyboardButton(text="🌐 Любой рейтинг", callback_data=SearchParam(param='rating', value='all').pack())],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=Action(name="cancel_fsm").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_search_period_keyboard():
    buttons = [
        [InlineKeyboardButton(text="За всё время", callback_data=SearchParam(param='period', value='all').pack())],
        [InlineKeyboardButton(text="За последний месяц",
                              callback_data=SearchParam(param='period', value='month').pack())],
        [InlineKeyboardButton(text="За последнюю неделю",
                              callback_data=SearchParam(param='period', value='week').pack())],
        [InlineKeyboardButton(text="За последний день", callback_data=SearchParam(param='period', value='day').pack())],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=Action(name="cancel_fsm").pack())]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_queries_menu(queries: list):
    """Создает меню для выбора существующего запроса или создания нового."""
    buttons = [
        [InlineKeyboardButton(text="🆕 Создать новый запрос", callback_data="create_new_query")]
    ]

    # Используем enumerate для нумерации кнопок, начиная с 1
    for i, query_source in enumerate(queries, 1):
        query_text = query_source.details.get('query', 'N/A')
        rating = query_source.details.get('rating', 'N/A').upper()

        # Текст кнопки теперь содержит номер и краткую информацию
        button_text = f"{i}. 🔍 {query_text[:25]}... ({rating})"

        buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=SourceSelect(source_id=query_source.source_id).pack()
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_export_options_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📊 Мои оценки", callback_data="export_mine")],
        [InlineKeyboardButton(text="👤 Оценки пользователя по ID", callback_data="export_specific_user")],
        [InlineKeyboardButton(text="🌐 Все оценки (всех пользователей)", callback_data="export_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=Action(name="cancel_fsm").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
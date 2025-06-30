from typing import Optional
from aiogram.filters.callback_data import CallbackData


class SourceSelect(CallbackData, prefix="src_select"):
    source_id: int


class ArtworkRate(CallbackData, prefix="art_rate"):
    source_id: int
    artwork_id: int
    score: int


class Action(CallbackData, prefix="action"):
    name: str
    source_id: Optional[int] = None


class SkipAction(CallbackData, prefix="skip"):
    action: str  # Будет 'image' или 'post'
    source_id: int
    post_idx: int  # Индекс поста, который мы пропускаем


class SearchParam(CallbackData, prefix="search_p"):
    param: str  # 'target', 'rating', 'period'
    value: str

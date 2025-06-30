# app/states/user_states.py
from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    waiting_for_password = State()


class UserContentStates(StatesGroup):
    waiting_for_file = State()


class PixivSearchStates(StatesGroup):
    waiting_for_keywords = State()
    waiting_for_target = State()
    waiting_for_rating = State()
    waiting_for_period = State()


class ExportStates(StatesGroup):
    waiting_for_user_id = State()

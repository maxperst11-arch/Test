from aiogram.fsm.state import State, StatesGroup


class NewTask(StatesGroup):
    title = State()
    topic = State()
    new_topic_name = State()
    importance = State()
    deadline = State()
    confirm = State()


class EditDeadline(StatesGroup):
    waiting = State()


class TopicInput(StatesGroup):
    name = State()
    rename = State()


class SettingsInput(StatesGroup):
    quiet = State()
    digest_time = State()
    timezone = State()

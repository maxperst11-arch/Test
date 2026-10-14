from aiogram.filters.callback_data import CallbackData


class NewTaskCb(CallbackData, prefix="nt"):
    action: str  # quick | topic | new_topic | importance | deadline | custom | save | cancel
    value: str | None = None


class ListCb(CallbackData, prefix="ls"):
    # topic_id: 0 — все задачи, -1 — без темы
    action: str  # show | filter | burning
    topic_id: int = 0


class TaskCb(CallbackData, prefix="tk"):
    action: str  # open | done | snooze | move | delete | delete_yes | back
    task_id: int
    value: str | None = None


class TopicCb(CallbackData, prefix="tp"):
    action: str  # list | open | add_section | add_sub | rename | delete | move_to
    topic_id: int = 0
    value: int = 0


class SettingsCb(CallbackData, prefix="st"):
    action: str  # quiet | digest | tz | tz_set | anger | evening
    value: str | None = None

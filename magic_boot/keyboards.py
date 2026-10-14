from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from magic_boot import texts
from magic_boot.callbacks import ListCb, NewTaskCb, SettingsCb, TaskCb, TopicCb
from magic_boot.db import Task, Topic
from magic_boot.render import ordered_topics, short_title

QUICK_DEADLINES = {
    "today": "Сегодня",
    "tomorrow": "Завтра",
    "3days": "Через 3 дня",
    "week": "Через неделю",
}

TIMEZONES = {
    "Europe/Kaliningrad": "Калининград (UTC+2)",
    "Europe/Moscow": "Москва (UTC+3)",
    "Europe/Samara": "Самара (UTC+4)",
    "Asia/Yekaterinburg": "Екатеринбург (UTC+5)",
    "Asia/Omsk": "Омск (UTC+6)",
    "Asia/Novosibirsk": "Новосибирск (UTC+7)",
    "Asia/Krasnoyarsk": "Красноярск (UTC+7)",
    "Asia/Irkutsk": "Иркутск (UTC+8)",
    "Asia/Vladivostok": "Владивосток (UTC+10)",
}


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [texts.MENU_TASKS, texts.MENU_BURNING],
        [texts.MENU_NEW_TASK, texts.MENU_TOPICS],
        [texts.MENU_SHAME, texts.MENU_SETTINGS],
        [texts.MENU_HELP],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
    )


def quick_task_offer() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, записать", callback_data=NewTaskCb(action="quick"))
    kb.button(text="Нет", callback_data=NewTaskCb(action="cancel"))
    return kb.as_markup()


def choose_topic(topics: list[Topic]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for topic in ordered_topics(topics):
        label = f"   · {topic.name}" if topic.parent_id else f"📁 {topic.name}"
        kb.button(text=label, callback_data=NewTaskCb(action="topic", value=str(topic.id)))
    kb.button(text=texts.NO_TOPIC, callback_data=NewTaskCb(action="topic", value="0"))
    kb.button(text="➕ Новая тема", callback_data=NewTaskCb(action="new_topic"))
    kb.button(text="✖️ Отмена", callback_data=NewTaskCb(action="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def choose_importance() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for value, label in texts.IMPORTANCE_LABELS.items():
        kb.button(text=label, callback_data=NewTaskCb(action="importance", value=str(value)))
    kb.button(text="✖️ Отмена", callback_data=NewTaskCb(action="cancel"))
    kb.adjust(3, 1)
    return kb.as_markup()


def choose_deadline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, label in QUICK_DEADLINES.items():
        kb.button(text=label, callback_data=NewTaskCb(action="deadline", value=key))
    kb.button(text="✖️ Отмена", callback_data=NewTaskCb(action="cancel"))
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def confirm_task() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сохранить", callback_data=NewTaskCb(action="save"))
    kb.button(text="✖️ Отмена", callback_data=NewTaskCb(action="cancel"))
    return kb.as_markup()


def task_list(tasks: list[Task], filtered: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for index, task in enumerate(tasks[:20], start=1):
        kb.button(
            text=f"{index}. {short_title(task.title)}",
            callback_data=TaskCb(action="open", task_id=task.id),
        )
    kb.button(text="🗂 Фильтр по теме", callback_data=ListCb(action="filter"))
    if filtered:
        kb.button(text="📋 Все задачи", callback_data=ListCb(action="show"))
    kb.adjust(1)
    return kb.as_markup()


def topic_filter(topics: list[Topic]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for topic in ordered_topics(topics):
        label = f"   · {topic.name}" if topic.parent_id else f"📁 {topic.name}"
        kb.button(text=label, callback_data=ListCb(action="show", topic_id=topic.id))
    kb.button(text=texts.NO_TOPIC, callback_data=ListCb(action="show", topic_id=-1))
    kb.button(text="📋 Все задачи", callback_data=ListCb(action="show"))
    kb.adjust(1)
    return kb.as_markup()


def task_card(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сделал", callback_data=TaskCb(action="done", task_id=task_id))
    kb.button(text="📅 Перенести срок", callback_data=TaskCb(action="move", task_id=task_id))
    kb.button(text="🗑 Удалить", callback_data=TaskCb(action="delete", task_id=task_id))
    kb.button(text="⬅️ К списку", callback_data=ListCb(action="show"))
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def reminder(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сделал", callback_data=TaskCb(action="done", task_id=task_id))
    kb.button(text="⏰ 1 ч", callback_data=TaskCb(action="snooze", task_id=task_id, value="1h"))
    kb.button(text="⏰ 3 ч", callback_data=TaskCb(action="snooze", task_id=task_id, value="3h"))
    kb.button(text="⏰ До завтра", callback_data=TaskCb(action="snooze", task_id=task_id, value="tomorrow"))
    kb.button(text="📅 Перенести срок", callback_data=TaskCb(action="move", task_id=task_id))
    kb.button(text="🗑 Удалить", callback_data=TaskCb(action="delete", task_id=task_id))
    kb.adjust(1, 3, 2)
    return kb.as_markup()


def confirm_delete(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Да, удалить", callback_data=TaskCb(action="delete_yes", task_id=task_id))
    kb.button(text="Нет", callback_data=TaskCb(action="open", task_id=task_id))
    return kb.as_markup()


def topics_menu(topics: list[Topic]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for topic in ordered_topics(topics):
        label = f"   · {topic.name}" if topic.parent_id else f"📁 {topic.name}"
        kb.button(text=label, callback_data=TopicCb(action="open", topic_id=topic.id))
    kb.button(text="➕ Новый раздел", callback_data=TopicCb(action="add_section"))
    kb.adjust(1)
    return kb.as_markup()


def topic_card(topic: Topic) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if topic.parent_id is None:
        kb.button(text="➕ Тема внутри", callback_data=TopicCb(action="add_sub", topic_id=topic.id))
    kb.button(text="✏️ Переименовать", callback_data=TopicCb(action="rename", topic_id=topic.id))
    kb.button(text="🗑 Удалить", callback_data=TopicCb(action="delete", topic_id=topic.id))
    kb.button(text="⬅️ К темам", callback_data=TopicCb(action="list"))
    kb.adjust(1)
    return kb.as_markup()


def topic_move_targets(topic: Topic, topics: list[Topic]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for target in ordered_topics(topics):
        if target.id == topic.id or target.parent_id == topic.id:
            continue
        label = f"   · {target.name}" if target.parent_id else f"📁 {target.name}"
        kb.button(text=label, callback_data=TopicCb(action="move_to", topic_id=topic.id, value=target.id))
    kb.button(text=texts.NO_TOPIC, callback_data=TopicCb(action="move_to", topic_id=topic.id, value=0))
    kb.button(text="✖️ Не удалять", callback_data=TopicCb(action="open", topic_id=topic.id))
    kb.adjust(1)
    return kb.as_markup()


def topic_confirm_delete(topic: Topic) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Да, удалить", callback_data=TopicCb(action="move_to", topic_id=topic.id, value=0))
    kb.button(text="Нет", callback_data=TopicCb(action="open", topic_id=topic.id))
    return kb.as_markup()


def settings(evening: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🌙 Тихие часы", callback_data=SettingsCb(action="quiet"))
    kb.button(text="🌅 Время сводки", callback_data=SettingsCb(action="digest"))
    kb.button(text="🕰 Часовой пояс", callback_data=SettingsCb(action="tz"))
    kb.button(text="😠 Сменить уровень злости", callback_data=SettingsCb(action="anger"))
    kb.button(
        text="🌆 Выключить вечерний отчёт" if evening else "🌆 Включить вечерний отчёт",
        callback_data=SettingsCb(action="evening"),
    )
    kb.adjust(2, 1, 1, 1)
    return kb.as_markup()


def timezones() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for zone, label in TIMEZONES.items():
        kb.button(text=label, callback_data=SettingsCb(action="tz_set", value=zone))
    kb.adjust(1)
    return kb.as_markup()

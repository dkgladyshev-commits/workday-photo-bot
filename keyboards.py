"""Inline-клавиатуры.

callback_data (компактные, заведомо < 64 байт):
  Категории:   cat:work | cat:personal | cat:break | cat:cancel
  Задача:      t:<a>:<o>:<task_id>
               a = p (пауза) | r (продолжить) | c (завершить)
               o = k (карточка задачи) | d (сообщение /today)
  Очистка:     clr:yes | clr:no
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder


def _truncate(text: str, n: int = 22) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def category_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Рабочая задача", callback_data="cat:work")
    kb.button(text="Личная задача", callback_data="cat:personal")
    kb.button(text="Перерыв", callback_data="cat:break")
    kb.button(text="Отмена", callback_data="cat:cancel")
    kb.adjust(1)
    return kb.as_markup()


def running_card_keyboard(task_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="⏸ Пауза", callback_data=f"t:p:k:{task_id}")
    kb.button(text="✅ Завершить", callback_data=f"t:c:k:{task_id}")
    kb.button(text="🔄 Обновить", callback_data=f"t:u:k:{task_id}")
    kb.adjust(2, 1)
    return kb.as_markup()


def paused_card_keyboard(task_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="▶️ Продолжить", callback_data=f"t:r:k:{task_id}")
    kb.button(text="✅ Завершить", callback_data=f"t:c:k:{task_id}")
    kb.adjust(2)
    return kb.as_markup()


def today_keyboard(tasks: list):
    """Единый блок кнопок внизу сообщения /today (вариант A).

    Кнопки только для running и paused задач; в тексте каждой — имя задачи.
    completed задачи кнопок не получают. Если активных/паузных нет -> None.
    """
    kb = InlineKeyboardBuilder()
    count = 0
    for t in tasks:
        name = _truncate(t["title"])
        tid = t["id"]
        if t["status"] == "running":
            kb.button(text=f"⏸ Пауза · {name}", callback_data=f"t:p:d:{tid}")
            kb.button(text=f"✅ Завершить · {name}", callback_data=f"t:c:d:{tid}")
            count += 2
        elif t["status"] == "paused":
            kb.button(text=f"▶️ Продолжить · {name}", callback_data=f"t:r:d:{tid}")
            kb.button(text=f"✅ Завершить · {name}", callback_data=f"t:c:d:{tid}")
            count += 2
    if count == 0:
        return None
    kb.adjust(1)
    return kb.as_markup()


def clear_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, очистить", callback_data="clr:yes")
    kb.button(text="Нет", callback_data="clr:no")
    kb.adjust(2)
    return kb.as_markup()

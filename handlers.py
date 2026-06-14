"""Хендлеры команд, текста и callback-кнопок.

Принципы:
- storage_lock держим ТОЛЬКО вокруг read-modify-write, без сетевых await внутри.
- После любого callback всегда вызываем cb.answer() (убрать spinner).
- Сообщения обновляем через edit_text; 'message is not modified' игнорируем.
"""

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import storage
from storage import get_today_key, storage_lock
from keyboards import (
    category_keyboard,
    clear_keyboard,
    paused_card_keyboard,
    running_card_keyboard,
    today_keyboard,
)
from utils import effective_seconds, format_duration, now_almaty

router = Router()

CATEGORY_NAMES = {
    "work": "Рабочая задача",
    "personal": "Личная задача",
    "break": "Перерыв",
}


# --- рендеринг -------------------------------------------------------------

def render_card(task: dict) -> str:
    now = now_almaty()
    cat = CATEGORY_NAMES.get(task["category"], task["category"])
    dur = format_duration(effective_seconds(task, now))
    if task["status"] == "running":
        return (
            f"▶️ Сейчас в работе:\n{task['title']}\n\n"
            f"Категория: {cat}\nВремя: {dur}"
        )
    if task["status"] == "paused":
        return (
            f"⏸ Задача на паузе:\n{task['title']}\n\n"
            f"Категория: {cat}\nНакопленное время: {dur}"
        )
    return (
        f"✅ Задача завершена:\n{task['title']}\n\n"
        f"Категория: {cat}\nИтоговое время: {dur}"
    )


def render_today(tasks: list) -> str:
    if not tasks:
        return (
            "Сегодня пока нет зафиксированных задач. "
            "Напишите задачу обычным сообщением."
        )
    now = now_almaty()
    running = [t for t in tasks if t["status"] == "running"]
    paused = [t for t in tasks if t["status"] == "paused"]
    completed = [t for t in tasks if t["status"] == "completed"]

    lines = [f"Фотография дня — {get_today_key()}", ""]

    if running:
        lines.append("▶️ В работе:")
        for t in running:
            lines.append(f"• {t['title']} — {format_duration(effective_seconds(t, now))}")
        lines.append("")
    if paused:
        lines.append("⏸ На паузе:")
        for t in paused:
            lines.append(f"• {t['title']} — {format_duration(effective_seconds(t, now))}")
        lines.append("")
    if completed:
        lines.append("✅ Завершено:")
        for t in completed:
            lines.append(f"• {t['title']} — {format_duration(effective_seconds(t, now))}")
        lines.append("")

    totals = {"work": 0, "personal": 0, "break": 0}
    for t in tasks:
        totals[t["category"]] += effective_seconds(t, now)
    total_all = sum(totals.values())

    lines.append("Итого:")
    lines.append(f"Рабочие задачи: {format_duration(totals['work'])}")
    lines.append(f"Личные задачи: {format_duration(totals['personal'])}")
    lines.append(f"Перерывы: {format_duration(totals['break'])}")
    lines.append(f"Общее зафиксированное время: {format_duration(total_all)}")
    return "\n".join(lines)


async def safe_edit(cb: CallbackQuery, text: str, reply_markup=None) -> None:
    """edit_text с проглатыванием 'not modified' и фолбэком на новое сообщение."""
    try:
        await cb.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        try:
            await cb.message.answer(text, reply_markup=reply_markup)
        except Exception:
            pass


# --- команды ---------------------------------------------------------------

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Это бот «Фотография рабочего дня».\n\n"
        "Напишите задачу обычным сообщением, выберите категорию — "
        "и бот начнёт фиксировать время.\n\n"
        "Команды:\n"
        "/today — фотография дня\n"
        "/active — текущая активная задача\n"
        "/pause — поставить активную задачу на паузу\n"
        "/stop — завершить активную задачу\n"
        "/clear — очистить сегодняшний список"
    )


@router.message(Command("today"))
async def cmd_today(message: Message):
    user_id = message.from_user.id
    async with storage_lock:
        data = storage.load_data()
        tasks = storage.get_today_tasks(data, user_id)
    await message.answer(render_today(tasks), reply_markup=today_keyboard(tasks))


@router.message(Command("active"))
async def cmd_active(message: Message):
    user_id = message.from_user.id
    async with storage_lock:
        data = storage.load_data()
        tasks = storage.get_today_tasks(data, user_id)
    running = [t for t in tasks if t["status"] == "running"]
    if not running:
        await message.answer("Сейчас нет активной задачи.")
        return
    task = running[0]
    await message.answer(render_card(task), reply_markup=running_card_keyboard(task["id"]))


@router.message(Command("pause"))
async def cmd_pause(message: Message):
    user_id = message.from_user.id
    task = None
    async with storage_lock:
        data = storage.load_data()
        running = [t for t in storage.get_today_tasks(data, user_id) if t["status"] == "running"]
        if running:
            storage.pause_task(data, user_id, running[0]["id"])
            storage.save_data(data)
            task = storage.find_task_by_id(data, user_id, running[0]["id"])
    if task is None:
        await message.answer("Нет активной задачи для паузы.")
    else:
        await message.answer(render_card(task), reply_markup=paused_card_keyboard(task["id"]))


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    user_id = message.from_user.id
    task = None
    async with storage_lock:
        data = storage.load_data()
        running = [t for t in storage.get_today_tasks(data, user_id) if t["status"] == "running"]
        if running:
            storage.complete_task(data, user_id, running[0]["id"])
            storage.save_data(data)
            task = storage.find_task_by_id(data, user_id, running[0]["id"])
    if task is None:
        await message.answer(
            "Нет активной задачи для завершения. "
            "Откройте /today, чтобы завершить задачу на паузе."
        )
    else:
        await message.answer(render_card(task))


@router.message(Command("clear"))
async def cmd_clear(message: Message):
    await message.answer("Точно очистить сегодняшний список?", reply_markup=clear_keyboard())


# --- обычный текст -> pending ----------------------------------------------

@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message):
    user_id = message.from_user.id
    title = (message.text or "").strip()
    if not title:
        return
    async with storage_lock:
        data = storage.load_data()
        had_pending = storage.get_pending_task(data, user_id) is not None
        storage.set_pending_task(data, user_id, title)
        storage.save_data(data)
    text = (
        "Предыдущая незавершённая задача заменена новой. Выберите категорию:"
        if had_pending
        else "Выберите категорию:"
    )
    await message.answer(text, reply_markup=category_keyboard())


# --- выбор категории -------------------------------------------------------

@router.callback_query(F.data.startswith("cat:"))
async def on_category(cb: CallbackQuery):
    user_id = cb.from_user.id
    action = cb.data.split(":", 1)[1]

    if action == "cancel":
        async with storage_lock:
            data = storage.load_data()
            storage.clear_pending_task(data, user_id)
            storage.save_data(data)
        await cb.answer()
        await safe_edit(cb, "Создание задачи отменено.")
        return

    task = None
    async with storage_lock:
        data = storage.load_data()
        pending = storage.get_pending_task(data, user_id)
        if pending:
            task = storage.add_task(data, user_id, pending["title"], action)
            storage.clear_pending_task(data, user_id)
            storage.save_data(data)

    if task is None:
        await cb.answer("Нет задачи для создания. Напишите её заново.", show_alert=False)
        await safe_edit(cb, "Создание задачи устарело. Напишите задачу заново.")
        return

    await cb.answer()
    await safe_edit(cb, render_card(task), reply_markup=running_card_keyboard(task["id"]))


# --- действия над задачей --------------------------------------------------

@router.callback_query(F.data.startswith("t:"))
async def on_task_action(cb: CallbackQuery):
    user_id = cb.from_user.id
    parts = cb.data.split(":", 3)  # ["t", action, origin, task_id]
    if len(parts) != 4:
        await cb.answer()
        return
    _, action, origin, task_id = parts

    async with storage_lock:
        data = storage.load_data()
        if action == "p":
            status, task = storage.pause_task(data, user_id, task_id)
        elif action == "r":
            status, task = storage.start_task(data, user_id, task_id)
        elif action == "c":
            status, task = storage.complete_task(data, user_id, task_id)
        else:
            status, task = "not_found", None
        if status == "ok":
            storage.save_data(data)
        today_tasks = storage.get_today_tasks(data, user_id)

    if status == "not_found":
        await cb.answer("Эта задача уже завершена или не найдена.", show_alert=False)
        return

    if status == "already_completed":
        await cb.answer("Эта задача уже завершена.", show_alert=False)
        # Перерисуем представление, чтобы убрать устаревшие кнопки.
        if origin == "d":
            await safe_edit(cb, render_today(today_tasks), reply_markup=today_keyboard(today_tasks))
        else:
            await safe_edit(cb, render_card(task), reply_markup=None)
        return

    await cb.answer()
    if origin == "d":
        # Действие из «пульта» /today -> пересобрать весь отчёт.
        await safe_edit(cb, render_today(today_tasks), reply_markup=today_keyboard(today_tasks))
    else:
        # Действие из карточки задачи -> обновить карточку.
        if task["status"] == "running":
            await safe_edit(cb, render_card(task), reply_markup=running_card_keyboard(task["id"]))
        elif task["status"] == "paused":
            await safe_edit(cb, render_card(task), reply_markup=paused_card_keyboard(task["id"]))
        else:
            await safe_edit(cb, render_card(task), reply_markup=None)


# --- очистка ---------------------------------------------------------------

@router.callback_query(F.data.startswith("clr:"))
async def on_clear(cb: CallbackQuery):
    user_id = cb.from_user.id
    action = cb.data.split(":", 1)[1]
    if action == "yes":
        async with storage_lock:
            data = storage.load_data()
            storage.clear_today(data, user_id)
            storage.save_data(data)
        await cb.answer()
        await safe_edit(cb, "Сегодняшний список очищен.")
    else:
        await cb.answer()
        await safe_edit(cb, "Очистка отменена.")

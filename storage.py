"""Работа с tasks.json.

Правило блокировки:
- load_data() и save_data() — "сырые" хелперы БЕЗ собственного lock.
- storage_lock берётся ОДИН раз на высокоуровневой операции в handlers,
  как единая критическая секция read-modify-write:

      async with storage_lock:
          data = load_data()
          ... изменить data через функции ниже ...
          save_data(data)

- Сами функции add_task / pause_task / complete_task / ... — синхронные,
  работают над уже загруженным data и lock не трогают.
  Так asyncio.Lock (нереентрантный) не захватывается дважды -> нет deadlock.

Multi-user:
- Каждая задача содержит user_id.
- Любой поиск running/paused идёт только среди задач конкретного user_id.
- Никогда не искать running-задачу глобально по всему JSON.
"""

import asyncio
import json
import os
import uuid

from utils import now_almaty, effective_seconds

DATA_FILE = os.path.join(os.path.dirname(__file__), "tasks.json")

# Единый глобальный замок на все операции с файлом.
storage_lock = asyncio.Lock()


# --- сырые хелперы (без lock) ---------------------------------------------

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"tasks": {}, "pending": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Битый файл не должен ронять бота — начинаем с чистой структуры.
        return {"tasks": {}, "pending": {}}
    data.setdefault("tasks", {})
    data.setdefault("pending", {})
    return data


def save_data(data: dict) -> None:
    # Атомарная запись через временный файл, чтобы не получить
    # полупустой tasks.json при сбое.
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


# --- ключи / выборки -------------------------------------------------------

def get_today_key() -> str:
    return now_almaty().strftime("%Y-%m-%d")


def _today_list(data: dict) -> list:
    """Список задач за сегодня (создаёт пустой при отсутствии)."""
    return data["tasks"].setdefault(get_today_key(), [])


def get_today_tasks(data: dict, user_id) -> list:
    uid = str(user_id)
    key = get_today_key()
    return [t for t in data["tasks"].get(key, []) if t["user_id"] == uid]


def find_task_by_id(data: dict, user_id, task_id: str):
    uid = str(user_id)
    for t in _today_list(data):
        if t["user_id"] == uid and t["id"] == task_id:
            return t
    return None


# --- pending ---------------------------------------------------------------

def get_pending_task(data: dict, user_id):
    return data["pending"].get(str(user_id))


def set_pending_task(data: dict, user_id, title: str) -> None:
    data["pending"][str(user_id)] = {
        "title": title,
        "created_at": now_almaty().isoformat(),
    }


def clear_pending_task(data: dict, user_id) -> None:
    data["pending"].pop(str(user_id), None)


# --- ядро логики времени ---------------------------------------------------

def pause_current_running_task(data: dict, user_id) -> None:
    """Снять с running текущую активную задачу ПОЛЬЗОВАТЕЛЯ (если есть).

    Только в пределах user_id. Банкуем время через effective_seconds.
    """
    uid = str(user_id)
    now = now_almaty()
    for t in _today_list(data):
        if t["user_id"] == uid and t["status"] == "running":
            t["accumulated_seconds"] = effective_seconds(t, now)
            t["status"] = "paused"
            t["last_started_at"] = None


def add_task(data: dict, user_id, title: str, category: str) -> dict:
    """Создать задачу и сразу запустить её (автостарт)."""
    pause_current_running_task(data, user_id)
    now = now_almaty()
    task = {
        "id": str(uuid.uuid4()),
        "user_id": str(user_id),
        "title": title,
        "category": category,
        "status": "running",
        "date": get_today_key(),
        "created_at": now.isoformat(),
        "last_started_at": now.isoformat(),
        "completed_at": None,
        "accumulated_seconds": 0,
    }
    _today_list(data).append(task)
    return task


def start_task(data: dict, user_id, task_id: str):
    """Продолжить paused-задачу. Возвращает (status, task).

    status: 'ok' | 'not_found' | 'already_completed'
    """
    task = find_task_by_id(data, user_id, task_id)
    if not task:
        return "not_found", None
    if task["status"] == "completed":
        return "already_completed", task
    # Сначала пауза текущей running (могла быть другая задача).
    pause_current_running_task(data, user_id)
    now = now_almaty()
    task["status"] = "running"
    task["last_started_at"] = now.isoformat()
    # accumulated_seconds НЕ трогаем — продолжаем копить дальше.
    return "ok", task


def pause_task(data: dict, user_id, task_id: str):
    """Поставить задачу на паузу. Возвращает (status, task)."""
    task = find_task_by_id(data, user_id, task_id)
    if not task:
        return "not_found", None
    if task["status"] == "completed":
        return "already_completed", task
    now = now_almaty()
    if task["status"] == "running":
        task["accumulated_seconds"] = effective_seconds(task, now)
    task["status"] = "paused"
    task["last_started_at"] = None
    return "ok", task


def complete_task(data: dict, user_id, task_id: str):
    """Завершить задачу. Возвращает (status, task).

    Если задача была running — банкуем остаток времени.
    Если paused — НИЧЕГО не добавляем (защита от двойного счёта).
    """
    task = find_task_by_id(data, user_id, task_id)
    if not task:
        return "not_found", None
    if task["status"] == "completed":
        return "already_completed", task
    now = now_almaty()
    if task["status"] == "running":
        task["accumulated_seconds"] = effective_seconds(task, now)
    task["status"] = "completed"
    task["completed_at"] = now.isoformat()
    task["last_started_at"] = None
    return "ok", task


def clear_today(data: dict, user_id) -> None:
    """Удалить задачи пользователя за сегодня + его pending."""
    uid = str(user_id)
    key = get_today_key()
    if key in data["tasks"]:
        data["tasks"][key] = [t for t in data["tasks"][key] if t["user_id"] != uid]
    data["pending"].pop(uid, None)

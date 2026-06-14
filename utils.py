"""Утилиты времени и форматирования.

Единый источник правды по времени — effective_seconds().
Нигде больше расчёт накопленного времени дублироваться не должен.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

ALMATY = ZoneInfo("Asia/Almaty")


def now_almaty() -> datetime:
    """Текущее время как timezone-aware datetime в Asia/Almaty."""
    return datetime.now(ALMATY)


def parse_iso(s: str) -> datetime:
    """Разобрать ISO-строку обратно в datetime (с таймзоной)."""
    return datetime.fromisoformat(s)


def format_duration(seconds) -> str:
    """Секунды -> 'HH:MM:SS'."""
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def effective_seconds(task: dict, now: datetime) -> int:
    """Фактически накопленное время задачи на момент now.

    - running: accumulated + (now - last_started_at)
    - любой другой статус: accumulated (ничего не добавляем)

    Этот helper используется и для отображения, и для финализации
    (пауза/завершение), поэтому повторного счёта быть не может.
    """
    if task["status"] == "running" and task.get("last_started_at"):
        started = parse_iso(task["last_started_at"])
        delta = int((now - started).total_seconds())
        if delta < 0:
            delta = 0
        return task["accumulated_seconds"] + delta
    return task["accumulated_seconds"]

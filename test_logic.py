"""Проверка логики времени без Telegram. Запуск: python test_logic.py"""

import tempfile, os
from datetime import datetime, timedelta

import utils
import storage

# Управляемые «часы».
CLOCK = {"now": datetime.fromisoformat("2026-06-14T10:00:00+05:00")}

def fake_now():
    return CLOCK["now"]

def tick(seconds):
    CLOCK["now"] = CLOCK["now"] + timedelta(seconds=seconds)

# Подменяем источник времени в обоих модулях.
utils.now_almaty = fake_now
storage.now_almaty = fake_now

# Изолированный файл данных.
fd, tmp = tempfile.mkstemp(suffix=".json")
os.close(fd)
os.remove(tmp)
storage.DATA_FILE = tmp

UID = 555

def secs(data, task_id):
    t = storage.find_task_by_id(data, UID, task_id)
    return utils.effective_seconds(t, fake_now())

def status(data, task_id, owner=UID):
    return storage.find_task_by_id(data, owner, task_id)["status"]

fails = []
def check(label, cond):
    print(("  OK  " if cond else " FAIL ") + label)
    if not cond:
        fails.append(label)

print("Сценарий 2: автопауза предыдущей при создании новой")
data = storage.load_data()
a = storage.add_task(data, UID, "Задача А", "work")          # t0
tick(60)                                                      # +60s
b = storage.add_task(data, UID, "Задача Б", "work")           # A -> pause, B -> run
storage.save_data(data)
check("A на паузе", status(data, a["id"]) == "paused")
check("B запущена", status(data, b["id"]) == "running")
check("A накопила ~60с", secs(data, a["id"]) == 60)
check("B накопила ~0с", secs(data, b["id"]) == 0)

print("\nСценарий 4: продолжение A ставит B на паузу")
tick(30)                                                      # +30s (B бежит)
st, _ = storage.start_task(data, UID, a["id"])               # A -> run, B -> pause
storage.save_data(data)
check("start вернул ok", st == "ok")
check("A запущена", status(data, a["id"]) == "running")
check("B на паузе", status(data, b["id"]) == "paused")
check("B накопила ~30с и не растёт", secs(data, b["id"]) == 30)
check("A осталась ~60с (accumulated сохранён)", secs(data, a["id"]) == 60)

print("\nСценарий 5: завершение paused-задачи не добавляет время второй раз")
b_before = secs(data, b["id"])                               # 30
tick(120)                                                     # время идёт, но B на паузе
st, _ = storage.complete_task(data, UID, b["id"])
storage.save_data(data)
check("complete вернул ok", st == "ok")
check("B завершена", status(data, b["id"]) == "completed")
check("B время не изменилось (=30)", secs(data, b["id"]) == b_before == 30)

print("\nДоп: повторный complete по завершённой -> already_completed, без изменения")
b_locked = secs(data, b["id"])
st, _ = storage.complete_task(data, UID, b["id"])
check("второй complete -> already_completed", st == "already_completed")
check("время по-прежнему 30", secs(data, b["id"]) == b_locked)

print("\nДоп: изоляция пользователей")
other = storage.add_task(data, 999, "Чужая", "personal")
storage.save_data(data)
mine = [t["title"] for t in storage.get_today_tasks(data, UID)]
check("чужая задача не видна UID", "Чужая" not in mine)
storage.pause_current_running_task(data, UID)               # не должна трогать чужую running
check("чужая running не сбита", status(data, other["id"], owner=999) == "running")

os.remove(tmp)
print("\n" + ("ВСЕ ТЕСТЫ ПРОШЛИ" if not fails else f"ПРОВАЛЕНО: {fails}"))
raise SystemExit(1 if fails else 0)

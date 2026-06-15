# workday_photo_bot — Claude Code guide

## What this project is

A single-user-friendly Telegram bot ("Фотография рабочего дня") that tracks time spent on tasks across three categories: work, personal, break. No database, no web UI — plain `tasks.json` file storage.

Stack: Python 3.12 + aiogram 3 + python-dotenv. Deployed on Railway (long-polling).

## Running locally

```bash
# one-time setup
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# copy token
cp .env.example .env          # then paste real token

python bot.py
```

**IMPORTANT:** Never run `bot.py` with the production token while Railway is active — only one polling instance can run at a time (TelegramConflictError). To test locally, either pause Railway or use a separate test bot token.

## Project layout

```
bot.py          entry point; polling loop only
handlers.py     all aiogram routes (commands, text, callbacks) + render helpers
storage.py      tasks.json I/O, business logic, asyncio.Lock
keyboards.py    inline keyboard builders
utils.py        now_almaty(), format_duration(), effective_seconds()
test_logic.py   offline unit-style tests (no Telegram needed)
```

## Key invariants

- `storage_lock` is acquired **once per handler** around the full read-modify-write cycle. `load_data` / `save_data` have no lock of their own.
- `effective_seconds(task, now)` is the single source of truth for elapsed time — used for display and for finalising (pause/complete).
- A user can have at most one `running` task at a time. Starting/resuming another auto-pauses the current one.
- Completing a `paused` task does NOT add time (prevents double-counting).
- All datetimes are timezone-aware in `Asia/Almaty`.
- `save_data` writes atomically via a `.tmp` file + `os.replace`.

## Running offline tests

```bash
python test_logic.py
```

## Deployment (Railway)

`Procfile` → `worker: python bot.py`

Env var required on Railway: `TELEGRAM_BOT_TOKEN`

## What is intentionally out of scope (MVP boundaries)

- Tasks spanning midnight count under creation date
- No editing title/category after creation
- No export or dashboard
- No webhook mode

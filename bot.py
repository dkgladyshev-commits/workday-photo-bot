"""Точка входа. Запуск long-polling."""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers import router


async def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        available = [k for k in os.environ if "TOKEN" in k or "TELEGRAM" in k]
        raise RuntimeError(
            f"TELEGRAM_BOT_TOKEN не задан. Переменные с TOKEN/TELEGRAM: {available}"
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = Bot(token)
    dp = Dispatcher()
    dp.include_router(router)

    logging.info("Бот запущен. Ожидание сообщений…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")

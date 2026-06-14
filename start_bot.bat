@echo off
title workday_photo_bot
cd /d "%~dp0"
echo Запуск бота @PhotoWorkingDayBot...
.venv\Scripts\python.exe bot.py
echo.
echo Бот остановлен. Нажмите любую клавишу для закрытия.
pause > nul

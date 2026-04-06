@echo off
chcp 65001 >nul
echo.
echo =====================================
echo  YouTube to Text - Запуск приложения
echo =====================================
echo.

REM Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Пожалуйста, установите Python 3.8+
    pause
    exit /b 1
)

echo ✅ Python найден

REM Проверяем зависимости
echo.
echo 📦 Проверка зависимостей...
pip list | find /i "fastapi" >nul 2>&1
if errorlevel 1 (
    echo ❌ Зависимости не установлены!
    echo.
    echo Установите их командой:
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo ✅ Зависимости установлены

REM Проверяем FFmpeg
echo.
echo 🎵 Проверка FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  FFmpeg не найден!
    echo Установите его с https://ffmpeg.org/download.html
    echo или через: choco install ffmpeg
    echo.
)

REM Запускаем приложение
echo.
echo 🚀 Запуск backend...
echo Сервер будет доступен по адресу: http://127.0.0.1:8000
echo.
echo Откройте frontend/index.html в браузере для использования приложения
echo.

cd backend
python -m uvicorn main:app --reload

pause

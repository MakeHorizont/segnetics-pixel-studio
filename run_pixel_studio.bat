@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Segnetics Pixel Studio - Universal Engineering Suite

echo ============================================================================
echo   SEGNETICS PIXEL STUDIO - ЦИФРОВОЙ ДВОЙНИК И ОПТИМИЗАТОР ПАМЯТИ ПЛК
echo   Поддержка: Segnetics Pixel 12xx / 25xx (ATmega2560)
echo ============================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ОШИБКА] Python 3 не найден в системе.
    echo Пожалуйста, установите Python 3.8+ с галочкой 'Add Python to PATH'.
    pause
    exit /b 1
)

:MENU
cls
echo ============================================================================
echo   SEGNETICS PIXEL STUDIO — ГЛАВНОЕ МЕНЮ
echo ============================================================================
echo   [1] Запуск веб-эмулятора Pixel Studio (Web UI: 18088, Modbus: 15502)
echo   [2] Аудит памяти проекта .psl на физические лимиты ATmega2560
echo   [3] Оптимизация проекта .psl (удаление анимаций, сжатие памяти)
echo   [4] Запуск полного набора автоматических тестов (19 тестов)
echo   [5] Инструкция: Как прошить программу в реальный контроллер по RS-485
echo   [0] Выход
echo ============================================================================
set /p choice="Выберите действие [0-5]: "

if "%choice%"=="1" goto RUN_STUDIO
if "%choice%"=="2" goto RUN_AUDIT
if "%choice%"=="3" goto RUN_OPTIMIZE
if "%choice%"=="4" goto RUN_TESTS
if "%choice%"=="5" goto RUN_FLASH_GUIDE
if "%choice%"=="0" exit /b 0

echo Неверный выбор. Попробуйте снова.
timeout /t 2 >nul
goto MENU

:RUN_STUDIO
cls
echo [Запуск] Запуск веб-студии Segnetics Pixel...
echo Сервер слушает: http://localhost:18088
echo Modbus TCP:     localhost:15502 (Unit ID: 1)
echo.
start "" "http://localhost:18088"
python -m src.pixel_studio.cli simulate --port 18088 --modbus-port 15502
pause
goto MENU

:RUN_AUDIT
cls
echo Введите путь к файлу проекта .psl (или перетащите файл мышкой сюда):
set /p pslpath="Путь: "
python -m src.pixel_studio.cli audit %pslpath%
echo.
pause
goto MENU

:RUN_OPTIMIZE
cls
echo Введите путь к исходному файлу .psl:
set /p inpath="Исходный файл: "
echo Введите путь для сохранения оптимизированного .psl:
set /p outpath="Выходной файл: "
python -m src.pixel_studio.cli optimize %inpath% %outpath%
echo.
pause
goto MENU

:RUN_TESTS
cls
echo [Тесты] Запуск набора тестов FBD, среды исполнения и цифрового двойника...
python run_tests.py
echo.
pause
goto MENU

:RUN_FLASH_GUIDE
cls
python -m src.pixel_studio.cli flash-guide
echo.
pause
goto MENU

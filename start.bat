@echo off
setlocal EnableExtensions
title PhotoGuard Launcher

rem Resolve every path from this file, so this copied project can run anywhere.
set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"

echo.
echo ========================================
echo        PhotoGuard - Local Launcher
echo ========================================
echo Project: %PROJECT_DIR%
echo.

if not exist "%BACKEND_DIR%\main.py" (
    echo ERROR: Backend file not found:
    echo %BACKEND_DIR%\main.py
    echo Make sure start.bat is in the PhotoGuard project folder.
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo ERROR: Python environment not found:
    echo %PYTHON_EXE%
    echo.
    echo In the backend folder, create it with:
    echo py -m venv .venv
    echo .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm was not found. Install Node.js, then run this file again.
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%\node_modules\vite\bin\vite.js" (
    echo ERROR: Frontend dependencies are not installed.
    echo.
    echo Run this once in the project folder:
    echo npm install
    pause
    exit /b 1
)

echo Starting website at http://127.0.0.1:5173 ...
rem Vite opens the browser only after its local server is ready.
start "PhotoGuard Frontend" /D "%PROJECT_DIR%" cmd /k "npm run dev -- --host 127.0.0.1 --open"

echo Starting backend API at http://127.0.0.1:8001 ...
start "PhotoGuard Backend" /D "%BACKEND_DIR%" cmd /k ""%PYTHON_EXE%" -m uvicorn main:app --host 127.0.0.1 --port 8001"

echo.
echo Services are starting in two separate windows.
echo MongoDB must be running locally for scan history and PDF reports.
echo The browser will open automatically when the website server is ready.
echo The AI model loads on the first analysis, keeping website startup fast.

endlocal

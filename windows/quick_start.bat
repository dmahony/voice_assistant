@echo off
REM Quick start script for Windows users
REM This script helps you set up and run the voice assistant

echo ========================================
echo Voice Assistant - Windows Quick Start
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo.

REM Check if requirements are installed
echo Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    echo Dependencies installed
    echo.
)

REM Check for binaries
echo Checking for bundled binaries...
if exist "bin\windows\ffmpeg.exe" (
    echo [OK] ffmpeg.exe found
) else (
    echo [WARN] ffmpeg.exe not found in bin\windows\
    echo        Audio conversion may not work
)

if exist "bin\windows\llama-server.exe" (
    echo [OK] llama-server.exe found
) else (
    echo [WARN] llama-server.exe not found in bin\windows\
    echo        LLM features will not be available
)

if exist "bin\windows\piper.exe" (
    echo [OK] piper.exe found
) else (
    echo [WARN] piper.exe not found in bin\windows\
    echo        TTS may not work properly
)

echo.

REM Run the app
echo Starting Voice Assistant...
echo.
python windows\run_windows.py

pause

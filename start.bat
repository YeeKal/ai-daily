@echo off

:: Start AI Daily News System

echo Starting AI Daily News System...
echo ====================================

:: Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please run install.bat first to create virtual environment and install dependencies
    pause
    exit /b 1
)

:: Start the project
echo Starting project...
echo Log output:
echo -----------------------------------
.venv\Scripts\python.exe -m src.main

echo -----------------------------------
echo Startup completed
pause
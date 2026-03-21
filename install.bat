@echo off

:: Install AI Daily News System

echo Installing AI Daily News System...
echo ====================================

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed!
    echo Please install Python 3.10 or higher first
    pause
    exit /b 1
)

:: Check if uv is installed
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: uv is not installed!
    echo Please install uv first: pip install uv
    pause
    exit /b 1
)

:: Create virtual environment
echo Creating Python 3.10 virtual environment...
uv venv --python 3.10
if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment!
    pause
    exit /b 1
)

echo Virtual environment created successfully

:: Install pip
echo Installing pip...
.venv\Scripts\python.exe -m ensurepip --upgrade
if %errorlevel% neq 0 (
    echo ERROR: Failed to install pip!
    pause
    exit /b 1
)

echo pip installed successfully

:: Install dependencies
echo Installing project dependencies...
.venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)

echo Dependencies installed successfully

:: Check .env file
if not exist ".env" (
    echo WARNING: .env file not found!
    echo Please create .env file based on .env.example and configure related parameters
)

echo ====================================
echo Installation completed!
echo You can now run start.bat to start the project
pause
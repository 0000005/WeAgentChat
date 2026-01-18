@echo off
cd /d %~dp0..\..
echo Activating virtual environment...
call server\venv\Scripts\activate

echo Starting Vectorization Script...
echo Please enter your SiliconFlow API Key when prompted.
python scripts\memory_test\vectorize_data.py

if %errorlevel% neq 0 (
    echo.
    echo Script failed with error code %errorlevel%.
)

pause

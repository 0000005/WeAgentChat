@echo off
cd /d %~dp0..\..
echo Activating virtual environment...
call server\venv\Scripts\activate

echo Starting Recall Testing Script...
echo Please enter your SiliconFlow API Key when prompted.
python scripts\memory_test\recall_test.py

if %errorlevel% neq 0 (
    echo.
    echo Script failed with error code %errorlevel%.
)

pause

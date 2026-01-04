@echo off
SETLOCAL
set BASE_DIR=%~dp0
cd /d %BASE_DIR%server

echo ========================================
echo   DouDouChat 数据库迁移生成工具
echo ========================================

if not exist venv\Scripts\alembic.exe (
    echo [错误] 未在 server/venv 中找到 Alembic。
    echo 请确保已安装依赖：pip install -r requirements.txt
    pause
    exit /b 1
)

set /p msg="请输入迁移描述 (例如: add_user_table): "

if "%msg%"=="" (
    echo [错误] 描述不能为空。
    pause
    exit /b 1
)

echo.
echo [Alembic] 正在对比模型并生成迁移脚本...
venv\Scripts\alembic -c alembic.ini revision --autogenerate -m "%msg%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [成功] 迁移脚本已生成在: server/alembic/versions/
    echo [提示] 下次启动程序时，该变更将自动应用到数据库。
) else (
    echo.
    echo [失败] 生成迁移脚本时出错。
)

echo ========================================
pause

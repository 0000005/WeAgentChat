@echo off
setlocal enabledelayedexpansion

set PROJECT_ROOT=%~dp0..
set BACKEND_EXE_NAME=wechatagent
set BACKEND_DIST=%PROJECT_ROOT%\build\backend
set BACKEND_WORK=%PROJECT_ROOT%\build\pyinstaller_work
set FRONT_DIR=%PROJECT_ROOT%\front

echo [1/6] Checking pnpm...
where pnpm >nul 2>nul
if errorlevel 1 (
  echo pnpm not found. Please install pnpm and re-run this script.
  exit /b 1
)

echo [2/6] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Please install Python 3.11+ and re-run this script.
  exit /b 1
)

echo [3/6] Checking PyInstaller...
pyinstaller --version >nul 2>nul
if errorlevel 1 (
  echo PyInstaller not found. Installing...
  python -m pip install pyinstaller
  if errorlevel 1 (
    echo Failed to install PyInstaller.
    exit /b 1
  )
)

echo [4/6] Building backend...
if exist "%BACKEND_DIST%" rmdir /s /q "%BACKEND_DIST%"
if exist "%BACKEND_WORK%" rmdir /s /q "%BACKEND_WORK%"

if exist "%PROJECT_ROOT%\server.spec" (
  pyinstaller "%PROJECT_ROOT%\server.spec" --distpath "%BACKEND_DIST%" --workpath "%BACKEND_WORK%"
) else if exist "%PROJECT_ROOT%\server\server.spec" (
  pyinstaller "%PROJECT_ROOT%\server\server.spec" --distpath "%BACKEND_DIST%" --workpath "%BACKEND_WORK%"
) else (
  pyinstaller "%PROJECT_ROOT%\server\app\cli.py" ^
    --name "%BACKEND_EXE_NAME%" ^
    --collect-data tiktoken ^
    --collect-data tiktoken_ext ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --distpath "%BACKEND_DIST%" ^
    --workpath "%BACKEND_WORK%"
)
if errorlevel 1 (
  echo Backend build failed.
  exit /b 1
)

echo [5/6] Building frontend...
pushd "%FRONT_DIR%"
if not exist "node_modules" (
  pnpm install
  if errorlevel 1 (
    echo pnpm install failed.
    popd
    exit /b 1
  )
)
pnpm build
if errorlevel 1 (
  echo Frontend build failed.
  popd
  exit /b 1
)
popd

echo [6/6] Packaging Electron app...
pushd "%PROJECT_ROOT%"
if not exist "node_modules" (
  pnpm install
  if errorlevel 1 (
    echo pnpm install failed at root.
    popd
    exit /b 1
  )
)
pnpm electron:build
if errorlevel 1 (
  echo Electron packaging failed.
  popd
  exit /b 1
)
popd

echo Done. Output in dist-electron\
exit /b 0

@echo off
setlocal EnableExtensions

cd /d "%~dp0.."

set "ROOT_DIR=%CD%"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"
set "WAIT_SECONDS=60"

call :ensure_backend
if errorlevel 1 goto :fail

call :ensure_frontend
if errorlevel 1 goto :fail

echo.
echo [INFO] Starting Electron...
npm run electron:dev
exit /b %errorlevel%

:ensure_backend
call :check_http "http://127.0.0.1:%BACKEND_PORT%/api/health"
if not errorlevel 1 (
  echo [INFO] Backend is already ready on port %BACKEND_PORT%.
  exit /b 0
)

echo [INFO] Backend is not ready. Starting backend service...
start "WeAgentChat Backend" /D "%ROOT_DIR%\server" cmd /k "venv\Scripts\python -m uvicorn app.main:app --reload --port %BACKEND_PORT%"
call :wait_http "http://127.0.0.1:%BACKEND_PORT%/api/health" "Backend"
exit /b %errorlevel%

:ensure_frontend
call :check_http "http://127.0.0.1:%FRONTEND_PORT%"
if not errorlevel 1 (
  echo [INFO] Frontend is already ready on port %FRONTEND_PORT%.
  exit /b 0
)

echo [INFO] Frontend is not ready. Starting frontend dev server...
start "WeAgentChat Frontend" /D "%ROOT_DIR%\front" cmd /k "pnpm dev --host 127.0.0.1 --port %FRONTEND_PORT%"
call :wait_http "http://127.0.0.1:%FRONTEND_PORT%" "Frontend"
exit /b %errorlevel%

:check_http
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $r = Invoke-WebRequest -UseBasicParsing '%~1' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }"
exit /b %errorlevel%

:wait_http
setlocal
set "TARGET_URL=%~1"
set "TARGET_NAME=%~2"
set /a ATTEMPTS=0

:wait_http_loop
call :check_http "%TARGET_URL%"
if not errorlevel 1 (
  echo [INFO] %TARGET_NAME% is ready.
  endlocal & exit /b 0
)

set /a ATTEMPTS+=1
if %ATTEMPTS% geq %WAIT_SECONDS% (
  echo [ERROR] %TARGET_NAME% failed to become ready within %WAIT_SECONDS% seconds.
  endlocal & exit /b 1
)

timeout /t 1 /nobreak >nul
goto :wait_http_loop

:fail
echo.
echo [ERROR] Electron dev startup aborted.
echo [ERROR] Check the backend/frontend terminal windows for detailed logs.
exit /b 1

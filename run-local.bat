@echo off
echo ========================================================
echo   Academic Pipeline Engine - local-first
echo ========================================================
echo This legacy mode does not enable account login or service jobs.
echo.

if exist ".venv\Scripts\python.exe" (set "APE_PYTHON=.venv\Scripts\python.exe") else (set "APE_PYTHON=python")
%APE_PYTHON% -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (%APE_PYTHON% -m pip install -e . || exit /b 1)

start "Academic PE Backend (local)" cmd /k "%APE_PYTHON% -m uvicorn academic_pe.server:app --reload --host 127.0.0.1 --port 8000"
pushd ui
where pnpm >nul 2>nul
if not errorlevel 1 (start "Academic PE Frontend (local)" cmd /k "pnpm run dev") else (start "Academic PE Frontend (local)" cmd /k "npm run dev")
popd
echo Local-first UI is starting: http://localhost:3000

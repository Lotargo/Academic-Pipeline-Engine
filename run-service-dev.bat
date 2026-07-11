@echo off
setlocal
echo ========================================================
echo   Academic Pipeline Engine - service-dev
echo ========================================================
echo This mode starts PostgreSQL, applies migrations and enables auth.
echo.

where docker >nul 2>nul
if errorlevel 1 (
    echo Docker Desktop is required for service-dev PostgreSQL.
    exit /b 1
)

set "APE_DEV_DB_CONTAINER=ape-dev-postgres"
set "APE_DEV_DB_PORT=54329"
if not defined APE_DATABASE_SYNC_URL set "APE_DATABASE_SYNC_URL=postgresql+psycopg://ape:ape_dev_password@127.0.0.1:%APE_DEV_DB_PORT%/ape"
if not defined APE_DATABASE_ASYNC_URL set "APE_DATABASE_ASYNC_URL=postgresql+asyncpg://ape:ape_dev_password@127.0.0.1:%APE_DEV_DB_PORT%/ape"
if not defined APE_AUTH_JWT_SECRET set "APE_AUTH_JWT_SECRET=local-development-auth-secret-2026-minimum-32-chars"

docker inspect "%APE_DEV_DB_CONTAINER%" >nul 2>nul
if errorlevel 1 (
    echo Creating local development PostgreSQL container...
    docker run --name "%APE_DEV_DB_CONTAINER%" -e POSTGRES_USER=ape -e POSTGRES_PASSWORD=ape_dev_password -e POSTGRES_DB=ape -p %APE_DEV_DB_PORT%:5432 -d postgres:16-alpine
    if errorlevel 1 exit /b 1
) else (
    docker start "%APE_DEV_DB_CONTAINER%" >nul
    if errorlevel 1 exit /b 1
)

echo Waiting for PostgreSQL...
for /l %%i in (1,1,30) do (
    docker exec "%APE_DEV_DB_CONTAINER%" pg_isready -U ape -d ape >nul 2>nul && goto :database_ready
    timeout /t 1 /nobreak >nul
)
echo PostgreSQL did not become ready.
exit /b 1

:database_ready
if exist ".venv\Scripts\python.exe" (
    set "APE_PYTHON=.venv\Scripts\python.exe"
) else (
    set "APE_PYTHON=python"
)

%APE_PYTHON% -c "import asyncpg, fastapi, psycopg, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo Installing backend dependencies...
    %APE_PYTHON% -m pip install -e . || exit /b 1
)

echo Applying database migrations...
%APE_PYTHON% -m alembic upgrade head || exit /b 1

echo Starting service-dev backend and frontend in separate windows...
start "Academic PE Backend (service-dev)" cmd /k "set APE_DATABASE_SYNC_URL=%APE_DATABASE_SYNC_URL%&& set APE_DATABASE_ASYNC_URL=%APE_DATABASE_ASYNC_URL%&& set APE_AUTH_JWT_SECRET=%APE_AUTH_JWT_SECRET%&& %APE_PYTHON% -m uvicorn academic_pe.server:app --reload --host 127.0.0.1 --port 8000"
pushd ui
where pnpm >nul 2>nul
if not errorlevel 1 (start "Academic PE Frontend (service-dev)" cmd /k "pnpm run dev") else (start "Academic PE Frontend (service-dev)" cmd /k "npm run dev")
popd

echo.
echo Service-dev is starting: http://localhost:3000
echo Auth API: http://localhost:8000/api/auth/login
echo Use run-local.bat only for the legacy local-first UI without account login.
endlocal

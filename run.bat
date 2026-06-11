@echo off
echo ========================================================
echo   Academic Pipeline Engine Launcher
echo ========================================================
echo.
echo Please choose how you want to run the application:
echo [1] Run with Docker Compose (Recommended - no local setup needed)
echo [2] Run locally (requires Python + uv/poetry and Node + pnpm)
echo [3] Exit
echo.
set /p choice="Enter choice (1-3): "

if "%choice%"=="1" (
    echo Starting with Docker Compose...
    docker compose up --build
    pause
    exit /b
)

if "%choice%"=="2" (
    echo Starting local deployment...
    
    :: Check if uv is available
    where uv >nul 2>nul
    if %errorlevel% equ 0 (
        echo Starting Backend API Server using uv...
        start "Academic PE Backend" cmd /c "uv run uvicorn academic_pe.server:app --host 0.0.0.0 --port 8000"
    ) else (
        echo Starting Backend API Server using python...
        start "Academic PE Backend" cmd /c "python -m uvicorn academic_pe.server:app --host 0.0.0.0 --port 8000"
    )
    
    :: Start frontend
    echo Starting Frontend Next.js app...
    cd ui
    where pnpm >nul 2>nul
    if %errorlevel% equ 0 (
        start "Academic PE Frontend" cmd /c "pnpm run dev"
    ) else (
        start "Academic PE Frontend" cmd /c "npm run dev"
    )
    cd ..
    
    echo.
    echo Application services started in separate windows.
    echo Backend API: http://localhost:8000
    echo Frontend UI: http://localhost:3000
    echo.
    pause
    exit /b
)

if "%choice%"=="3" (
    exit /b
)

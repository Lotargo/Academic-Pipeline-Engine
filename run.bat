@echo off
echo ========================================================
echo   Academic Pipeline Engine Launcher
echo   Starting local deployment...
echo ========================================================
echo.

:: Prefer the project virtual environment when it exists
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import fastapi, uvicorn, yaml, docx, requests, jinja2, fitz" >nul 2>nul
    if errorlevel 1 (
        echo Installing missing Backend Python dependencies into .venv...
        .venv\Scripts\python.exe -m pip install -e .
        if errorlevel 1 (
            echo Failed to install Backend Python dependencies.
            pause
            exit /b 1
        )
    )
    echo Starting Backend API Server using .venv...
    start "Academic PE Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn academic_pe.server:app --host 0.0.0.0 --port 8000"
) else (
    :: Check if uv is available
    where uv >nul 2>nul
    if not errorlevel 1 (
        uv run python -c "import fastapi, uvicorn, yaml, docx, requests, jinja2, fitz" >nul 2>nul
        if errorlevel 1 (
            echo Installing missing Backend Python dependencies using uv...
            uv pip install -e .
            if errorlevel 1 (
                echo Failed to install Backend Python dependencies.
                pause
                exit /b 1
            )
        )
        echo Starting Backend API Server using uv...
        start "Academic PE Backend" cmd /k "uv run uvicorn academic_pe.server:app --host 0.0.0.0 --port 8000"
    ) else (
        python -c "import fastapi, uvicorn, yaml, docx, requests, jinja2, fitz" >nul 2>nul
        if errorlevel 1 (
            echo Installing missing Backend Python dependencies using python...
            python -m pip install -e .
            if errorlevel 1 (
                echo Failed to install Backend Python dependencies.
                pause
                exit /b 1
            )
        )
        echo Starting Backend API Server using python...
        start "Academic PE Backend" cmd /k "python -m uvicorn academic_pe.server:app --host 0.0.0.0 --port 8000"
    )
)

:: Start frontend
echo Starting Frontend Next.js app...
cd ui
where pnpm >nul 2>nul
if not errorlevel 1 (
    start "Academic PE Frontend" cmd /k "pnpm run dev"
) else (
    start "Academic PE Frontend" cmd /k "npm run dev"
)
cd ..

echo.
echo Application services started in separate windows.
echo Backend API: http://localhost:8000
echo Frontend UI: http://localhost:3000
echo.
pause
exit /b

#!/bin/bash

echo "========================================================"
echo "  Academic Pipeline Engine Launcher"
echo "========================================================"
echo

echo "Please choose how you want to run the application:"
echo "[1] Run with Docker Compose (Recommended - no local setup needed)"
echo "[2] Run locally (requires Python + uv/poetry and Node + pnpm)"
echo "[3] Exit"
echo
read -p "Enter choice (1-3): " choice

if [ "$choice" = "1" ]; then
    echo "Starting with Docker Compose..."
    docker compose up --build
elif [ "$choice" = "2" ]; then
    echo "Starting local deployment..."
    
    # Run backend
    if command -v uv &> /dev/null; then
        echo "Starting Backend API Server using uv..."
        uv run uvicorn academic_pe.server:app --host 0.0.0.0 --port 8000 &
        BACKEND_PID=$!
    else
        echo "Starting Backend API Server using python..."
        python3 -m uvicorn academic_pe.server:app --host 0.0.0.0 --port 8000 &
        BACKEND_PID=$!
    fi
    
    # Run frontend
    echo "Starting Frontend Next.js app..."
    cd ui
    if command -v pnpm &> /dev/null; then
        pnpm run dev &
        FRONTEND_PID=$!
    else
        npm run dev &
        FRONTEND_PID=$!
    fi
    cd ..
    
    echo
    echo "Application services started."
    echo "Backend PID: $BACKEND_PID, Frontend PID: $FRONTEND_PID"
    echo "Backend API: http://localhost:8000"
    echo "Frontend UI: http://localhost:3000"
    echo "Press Ctrl+C to stop both services."
    
    # Cleanup on exit
    trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM
    wait
else
    exit 0
fi

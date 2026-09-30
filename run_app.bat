@echo off
echo ============================================
echo   AquaWatch Flood — Starting Application
echo ============================================
echo.

REM Install dependencies if needed
pip install -r requirements.txt --quiet

echo.
echo Starting FastAPI server on http://127.0.0.1:8000 ...
echo Press Ctrl+C to stop.
echo.

uvicorn main:app --reload --host 127.0.0.1 --port 8000

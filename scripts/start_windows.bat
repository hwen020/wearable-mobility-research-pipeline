@echo off
setlocal
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  if defined MOBILITY_PYTHON (
    "%MOBILITY_PYTHON%" -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
  if errorlevel 1 (echo Python 3 not found. Install Python 3.11+ first. & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency install failed. & pause & exit /b 1)
python -m app.demo_seed
if errorlevel 1 (echo Demo seeding failed. & pause & exit /b 1)
echo.
echo Open http://127.0.0.1:8000 in a browser
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause

@echo off
setlocal
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (echo Run scripts\start_windows.bat first. & pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
python -m pytest -q
exit /b %errorlevel%

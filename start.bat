@echo off
REM Jarvis unter Windows starten
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
if not exist .env copy .env.example .env
start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:8340"
.venv\Scripts\python server.py %*

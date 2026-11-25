@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set HF_HUB_DISABLE_TELEMETRY=1
python serveur.py
pause

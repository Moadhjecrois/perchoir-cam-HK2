@echo off
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
if not exist venv (%PY% -m venv venv)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python preparer_hors_ligne.py
pause

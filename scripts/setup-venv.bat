@echo off
setlocal enabledelayedexpansion

if not exist ".venv" (
  echo [+] Creating virtual environment
  python -m venv .venv
)

call .venv\Scripts\activate

echo [+] Upgrading pip
python -m pip install --upgrade pip

echo [+] Installing dependencies
pip install -r requirements.txt

echo [+] Done. Activate with: call .venv\Scripts\activate
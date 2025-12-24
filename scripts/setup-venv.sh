#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"

if [ ! -d ".venv" ]; then
  echo "[+] Creating virtual environment"
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[+] Upgrading pip"
python -m pip install --upgrade pip

echo "[+] Installing dependencies"
pip install -r requirements.txt

echo "[+] Done. Activate with: source .venv/bin/activate"
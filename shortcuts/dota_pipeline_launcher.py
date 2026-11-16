"""Compatibility wrapper for the main interactive CLI.

The real menu lives in scripts/dota_cli.py and is launched by dota.cmd.
This wrapper keeps the old Scripts Manager entry point working.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
exe = str(PYTHON) if PYTHON.exists() else sys.executable
raise SystemExit(subprocess.call([exe, str(ROOT / "scripts" / "dota_cli.py")], cwd=str(ROOT)))

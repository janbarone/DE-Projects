"""DOTA Pipeline launcher (Python version) — for use inside the Scripts Manager.

Same menu as the DOTA_Pipeline_Launcher.bat, but this runs as a .py script so
the Scripts Manager can host it in a tab: the input box feeds stdin (menu
choices) and stdout streams live.

It always invokes the project's own .venv python/dbt explicitly, so it works no
matter which Python interpreter the Scripts Manager itself uses.

Run standalone too:  python shortcuts/dota_pipeline_launcher.py
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
DBT = ROOT / ".venv" / "Scripts" / "dbt.exe"

MENU = "\n".join([
    "=" * 64,
    "   DOTA 2 Pipeline - Launcher",
    f"   {ROOT}",
    "-" * 64,
    "   [1] Incremental update   - load new scrape + dbt build",
    "   [2] Full rebuild+refresh - dbt build --full-refresh",
    "   [3] Scrape new matches   - interactive fetcher (data/)",
    "   [4] Refresh constants    - heroes / items / abilities",
    "   [5] Full pipeline        - constants + load + build + backup",
    "   [6] dbt tests only",
    "   [7] Backup database      - pg_dump snapshot (backups/)",
    "   [8] Start Postgres       - docker compose up -d",
    "   [9] Open Power BI report",
    "   [0] Exit",
    "=" * 64,
])


def run(cmd, cwd=ROOT):
    """Run a command, streaming output, and report pass/fail."""
    print(f"\n$ {' '.join(str(c) for c in cmd)}\n", flush=True)
    proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd))
    print("\n>>> OK\n" if proc.returncode == 0
          else f"\n>>> FAILED (exit {proc.returncode})\n", flush=True)
    return proc.returncode


def main():
    while True:
        print(MENU, flush=True)
        try:
            choice = input("Select an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.", flush=True)
            return

        if choice == "1":
            run([PY, "scripts/load_bronze.py", "--data-dir", "data"])
            run([DBT, "build", "--profiles-dir", ".", "--project-dir",
                 "transform", "--threads", "1"])
        elif choice == "2":
            run([DBT, "build", "--profiles-dir", ".", "--project-dir",
                 "transform", "--threads", "1", "--full-refresh"])
        elif choice == "3":
            run([PY, "data/_fetch_matches.py"])
        elif choice == "4":
            run([PY, "data/_fetch_constants.py", "--data-dir", "data"])
        elif choice == "5":
            run([PY, "scripts/run_pipeline.py", "--data-dir", "data",
                 "--refresh-constants", "--backup"])
        elif choice == "6":
            run([DBT, "test", "--profiles-dir", ".", "--project-dir",
                 "transform", "--threads", "1"])
        elif choice == "7":
            run([PY, "scripts/run_pipeline.py", "--only-backup",
                 "--backup-docker"])
        elif choice == "8":
            run(["docker", "compose", "up", "-d"])
            run(["docker", "ps"])
        elif choice == "9":
            pbip = ROOT / ".pbip" / "dota pipeline.pbip"
            print(f"\nOpening {pbip} ...\n", flush=True)
            if hasattr(os, "startfile"):
                os.startfile(pbip)
            else:
                subprocess.Popen(["cmd", "/c", "start", "", str(pbip)])
        elif choice == "0":
            print("\nBye.", flush=True)
            return
        else:
            print("\nInvalid choice.\n", flush=True)


if __name__ == "__main__":
    main()

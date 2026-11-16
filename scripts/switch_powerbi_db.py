"""Point the PBIP semantic model at a Postgres database.

Power BI must be closed, otherwise Desktop can overwrite hand-edited files.

Usage:
    python scripts/switch_powerbi_db.py --database dota_demo
    python scripts/switch_powerbi_db.py --database dota
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / ".pbip" / "dota pipeline.SemanticModel" / "definition" / "tables"
PATTERN = re.compile(r'PostgreSQL\.Database\("localhost",\s*"[^"]+"\)')


def powerbi_running() -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq PBIDesktop.exe"],
        capture_output=True, text=True, check=False,
    )
    return "PBIDesktop.exe" in result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Switch the Power BI PBIP Postgres database.")
    parser.add_argument("--database", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="edit even if Power BI is running")
    args = parser.parse_args()

    if powerbi_running() and not args.force:
        raise SystemExit("Power BI Desktop is running. Close it first (or use --force).")
    if not TABLES.exists():
        raise SystemExit(f"TMDL tables folder not found: {TABLES}")

    changed = 0
    for path in sorted(TABLES.glob("*.tmdl")):
        text = path.read_text(encoding="utf-8")
        new, count = PATTERN.subn(f'PostgreSQL.Database("localhost", "{args.database}")', text)
        if count:
            changed += count
            if not args.dry_run:
                path.write_text(new, encoding="utf-8")
    print(f"{'would update' if args.dry_run else 'updated'} {changed} table source(s) to database={args.database}")


if __name__ == "__main__":
    main()

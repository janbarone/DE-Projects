"""Single entrypoint wiring ingestion -> dbt build -> dbt test.

This is the "thin" shared runner that both orchestrators (Dagster / Airflow)
and humans call, so the pipeline logic lives in exactly one place.

Steps (default):
  1. python scripts/load_bronze.py --data-dir <data_dir>
  2. dbt build --profiles-dir <profiles_dir> --project-dir transform

Usage:
    python scripts/run_pipeline.py                       # full run
    python scripts/run_pipeline.py --data-dir sample_data
    python scripts/run_pipeline.py --only-load            # ingestion only
    python scripts/run_pipeline.py --only-dbt             # transforms only
    python scripts/run_pipeline.py --full-refresh         # rebuild incrementals
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "data"))

from dota_common import get_logger  # noqa: E402

logger = get_logger("dota.run_pipeline")


def _find_dbt() -> str:
    """Locate the dbt executable (PATH first, then the repo venv)."""
    exe = shutil.which("dbt")
    if exe:
        return exe
    candidates = [
        BASE / ".venv" / "Scripts" / "dbt.exe",
        BASE / ".venv" / "bin" / "dbt",
        BASE / ".venv" / "Scripts" / "dbt",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise SystemExit("dbt executable not found on PATH or in .venv")


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    logger.info("run command=%s", " ".join(str(c) for c in cmd))
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=full_env)
    if proc.returncode != 0:
        raise SystemExit(f"command failed (exit {proc.returncode}): {' '.join(map(str, cmd))}")


def load_bronze(python: str, data_dir: Path) -> None:
    run([python, str(BASE / "scripts" / "load_bronze.py"), "--data-dir", str(data_dir)], cwd=BASE)


def dbt_build(dbt: str, profiles_dir: Path, project_dir: Path, full_refresh: bool) -> None:
    cmd = [dbt, "build", "--profiles-dir", str(profiles_dir), "--project-dir", str(project_dir)]
    if full_refresh:
        cmd.append("--full-refresh")
    run(cmd, cwd=BASE)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the full DOTA pipeline (load -> dbt).")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--dbt", default=None, help="dbt executable (auto-detected if omitted)")
    ap.add_argument("--data-dir", default=str(BASE / "data"))
    ap.add_argument("--profiles-dir", default=str(BASE))
    ap.add_argument("--project-dir", default=str(BASE / "transform"))
    ap.add_argument("--full-refresh", action="store_true")
    ap.add_argument("--only-load", action="store_true", help="run ingestion only, skip dbt")
    ap.add_argument("--only-dbt", action="store_true", help="run dbt only, skip ingestion")
    args = ap.parse_args()

    dbt = args.dbt or _find_dbt()
    data_dir = Path(args.data_dir)
    profiles_dir = Path(args.profiles_dir)
    project_dir = Path(args.project_dir)

    if not args.only_dbt:
        load_bronze(args.python, data_dir)
    if not args.only_load:
        dbt_build(dbt, profiles_dir, project_dir, args.full_refresh)

    logger.info("pipeline complete data_dir=%s", data_dir)


if __name__ == "__main__":
    main()

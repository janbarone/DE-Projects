"""Single entrypoint wiring ingestion -> dbt build -> dbt test -> pg_dump.

This is the "thin" shared runner that both orchestrators (Dagster / Airflow)
and humans call, so the pipeline logic lives in exactly one place.

Steps (default with --backup):
  1. python scripts/load_bronze.py --data-dir <data_dir>
  2. dbt build --profiles-dir <profiles_dir> --project-dir transform
  3. pg_dump -> backups/<prefix>_YYYYMMDD_HHMMSS.dump

Usage:
    python scripts/run_pipeline.py                       # load + dbt
    python scripts/run_pipeline.py --data-dir sample_data
    python scripts/run_pipeline.py --only-load            # ingestion only
    python scripts/run_pipeline.py --only-dbt             # transforms only
    python scripts/run_pipeline.py --backup               # + pg_dump snapshot
    python scripts/run_pipeline.py --only-backup          # pg_dump only
    python scripts/run_pipeline.py --full-refresh         # rebuild incrementals
"""
import argparse
import datetime as _dt
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


def dbt_source_freshness(dbt: str, profiles_dir: Path, project_dir: Path) -> None:
    """Run `dbt source freshness` (warn/error thresholds from sources.yml)."""
    cmd = [
        dbt,
        "source",
        "freshness",
        "--profiles-dir",
        str(profiles_dir),
        "--project-dir",
        str(project_dir),
    ]
    run(cmd, cwd=BASE)


def _find_pg_dump() -> str:
    """Locate pg_dump (PATH first, then the PG_DUMP env var)."""
    exe = shutil.which("pg_dump")
    if exe:
        return exe
    override = os.environ.get("PG_DUMP")
    if override and Path(override).expanduser().is_file():
        return override
    raise SystemExit(
        "pg_dump not found on PATH and PG_DUMP not set; install postgresql-client "
        "or point PG_DUMP at the binary."
    )


def _docker_pg_dump(out_file: Path) -> None:
    """Fallback: stream pg_dump out of the running dota_postgres container."""
    if not shutil.which("docker"):
        raise SystemExit("pg_dump and docker both unavailable")
    probe = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", "dota_postgres"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        raise SystemExit("dota_postgres container is not running")
    cmd = ["docker", "exec", "dota_postgres", "pg_dump", "-U", "postgres", "-d", "dota", "-Fc"]
    logger.info("run command=%s", " ".join(cmd))
    with out_file.open("wb") as fh:
        proc = subprocess.run(cmd, stdout=fh)
    if proc.returncode != 0:
        raise SystemExit(f"pg_dump failed (exit {proc.returncode})")


def backup_db(backups_dir: Path, prefix: str, use_docker: bool) -> Path:
    """Snapshot the dota database into backups/<prefix>_<ts>.dump."""
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = backups_dir / f"{prefix}_{stamp}.dump"
    if use_docker:
        _docker_pg_dump(out_file)
    else:
        pg_dump = _find_pg_dump()
        cmd = [pg_dump, "-U", "postgres", "-d", "dota", "-Fc", "-f", str(out_file)]
        run(cmd, cwd=BASE)
    logger.info("backup written backups=%s", out_file)
    return out_file


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the full DOTA pipeline (load -> dbt -> backup).")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--dbt", default=None, help="dbt executable (auto-detected if omitted)")
    ap.add_argument("--data-dir", default=str(BASE / "data"))
    ap.add_argument("--profiles-dir", default=str(BASE))
    ap.add_argument("--project-dir", default=str(BASE / "transform"))
    ap.add_argument("--full-refresh", action="store_true")
    ap.add_argument("--only-load", action="store_true", help="run ingestion only, skip dbt")
    ap.add_argument("--only-dbt", action="store_true", help="run dbt only, skip ingestion")
    ap.add_argument(
        "--backup",
        action="store_true",
        help="after dbt, snapshot the database with pg_dump (backups/<prefix>_<ts>.dump)",
    )
    ap.add_argument(
        "--only-backup",
        action="store_true",
        help="run only the pg_dump snapshot, skipping ingestion and dbt",
    )
    ap.add_argument(
        "--freshness",
        action="store_true",
        help="after dbt, run `dbt source freshness` against bronze sources",
    )
    ap.add_argument(
        "--only-freshness",
        action="store_true",
        help="run only `dbt source freshness`, skipping ingestion, dbt and backup",
    )
    ap.add_argument(
        "--backup-prefix",
        default="gold",
        help="filename prefix for pg_dump snapshots (default: gold)",
    )
    ap.add_argument(
        "--backups-dir",
        default=str(BASE / "backups"),
        help="directory for pg_dump snapshots (default: <repo>/backups)",
    )
    ap.add_argument(
        "--backup-docker",
        action="store_true",
        help="run pg_dump inside the dota_postgres container (docker exec fallback)",
    )
    args = ap.parse_args()

    backups_dir = Path(args.backups_dir)

    if args.only_backup:
        backup_db(backups_dir, args.backup_prefix, args.backup_docker)
        return
    if args.only_freshness:
        dbt = args.dbt or _find_dbt()
        dbt_source_freshness(dbt, Path(args.profiles_dir), Path(args.project_dir))
        return

    dbt = args.dbt or _find_dbt()
    data_dir = Path(args.data_dir)
    profiles_dir = Path(args.profiles_dir)
    project_dir = Path(args.project_dir)

    if not args.only_dbt:
        load_bronze(args.python, data_dir)
    if not args.only_load:
        dbt_build(dbt, profiles_dir, project_dir, args.full_refresh)
    if args.freshness:
        dbt_source_freshness(dbt, profiles_dir, project_dir)
    if args.backup:
        backup_db(backups_dir, args.backup_prefix, args.backup_docker)

    logger.info("pipeline complete data_dir=%s", data_dir)


if __name__ == "__main__":
    main()

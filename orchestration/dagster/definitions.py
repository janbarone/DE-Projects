"""Dagster definitions for the DOTA medallion pipeline.

Four assets:
  bronze_loaded         ->  python scripts/run_pipeline.py --only-load
  dbt_built             ->  python scripts/run_pipeline.py --only-dbt   (deps on bronze_loaded)
  source_freshness      ->  python scripts/run_pipeline.py --only-freshness (deps on dbt_built)
  db_backed_up          ->  python scripts/run_pipeline.py --only-backup (deps on dbt_built)

Plus a daily schedule. Run locally with:  dagster dev -m definitions
(or `dagster dev` from this directory).
"""
import os
import subprocess
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    Definitions,
    ScheduleDefinition,
    asset,
    define_asset_job,
)

# repo root is two levels up from orchestration/dagster/
REPO = Path(__file__).resolve().parents[2]
DATA_DIR = os.environ.get("DOTA_DATA_DIR", "sample_data")
PYTHON = os.environ.get("DOTA_PYTHON", "python")


def _run(context: AssetExecutionContext, *args: str) -> None:
    cmd = [PYTHON, str(REPO / "scripts" / "run_pipeline.py"), *args]
    context.log.info(f"running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=REPO, check=False)
    if result.returncode != 0:
        raise Exception(f"pipeline step failed (exit {result.returncode}): {' '.join(cmd)}")


@asset(description="Load raw JSON (sample or live scrape) into PostgreSQL bronze.")
def bronze_loaded(context: AssetExecutionContext) -> None:
    _run(context, "--only-load", "--data-dir", DATA_DIR)


@asset(description="Build silver + gold with dbt and run dbt tests.", deps=["bronze_loaded"])
def dbt_built(context: AssetExecutionContext) -> None:
    _run(context, "--only-dbt")


@asset(
    description="Check bronze source freshness against warn/error thresholds.",
    deps=["dbt_built"],
)
def source_freshness(context: AssetExecutionContext) -> None:
    _run(context, "--only-freshness")


@asset(
    description="Snapshot the database with pg_dump into backups/ (daily savepoint).",
    deps=["dbt_built"],
)
def db_backed_up(context: AssetExecutionContext) -> None:
    _run(context, "--only-backup", "--backup-docker")


daily_job = define_asset_job("daily_medallion_refresh", selection="*")

daily_schedule = ScheduleDefinition(job=daily_job, cron_schedule="0 3 * * *")

defs = Definitions(
    assets=[bronze_loaded, dbt_built, source_freshness, db_backed_up],
    jobs=[daily_job],
    schedules=[daily_schedule],
)

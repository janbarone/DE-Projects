"""Airflow DAG for the DOTA medallion pipeline.

Four tasks wired as a DAG:
  load_bronze  (ingestion)  ->  dbt_build  (silver + gold + tests)
                                   |-> dbt_source_freshness  (monitor bronze)
                                   |-> pg_dump_backup        (backups/)

All tasks shell out to the shared `scripts/run_pipeline.py` so the pipeline
logic is defined once, not duplicated in the orchestrator.

The backup step streams pg_dump out of the running `dota_postgres` container
(--backup-docker) because the orchestrator image does not ship a pg_dump
binary. `backups/` is a repo mount inside the container (/opt/dota/backups),
so the dump lands on the host like a manual `pg_dump`.

Replace BashOperator with the dbt-cosmos provider for a first-class dbt
integration if preferred (adds astronomer-cosmos + dbt-postgres to the image).
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="dota_medallion_pipeline",
    default_args=default_args,
    description="OpenDota -> bronze -> dbt silver/gold -> pg_dump -> Power BI",
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["dota", "medallion", "dbt"],
) as dag:

    load_bronze = BashOperator(
        task_id="load_bronze",
        bash_command=(
            "python /opt/dota/scripts/run_pipeline.py --only-load "
            "--data-dir {{ var.value.get('data_dir', 'sample_data') }}"
        ),
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            "python /opt/dota/scripts/run_pipeline.py --only-dbt "
            "--profiles-dir /opt/dota --project-dir /opt/dota/transform"
        ),
    )

    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=(
            "python /opt/dota/scripts/run_pipeline.py --only-freshness "
            "--profiles-dir /opt/dota --project-dir /opt/dota/transform"
        ),
    )

    pg_dump_backup = BashOperator(
        task_id="pg_dump_backup",
        bash_command=(
            "python /opt/dota/scripts/run_pipeline.py --only-backup "
            "--backups-dir /opt/dota/backups --backup-prefix gold --backup-docker"
        ),
    )

    load_bronze >> dbt_build >> [dbt_source_freshness, pg_dump_backup]

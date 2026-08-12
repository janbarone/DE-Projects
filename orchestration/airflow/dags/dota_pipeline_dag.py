"""Airflow DAG for the DOTA medallion pipeline.

Two tasks wired as a DAG:
  load_bronze  (ingestion)  ->  dbt_build  (silver + gold + tests)

Both tasks shell out to the shared `scripts/run_pipeline.py` so the pipeline
logic is defined once, not duplicated in the orchestrator.

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
    description="OpenDota -> bronze -> dbt silver/gold -> Power BI",
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

    load_bronze >> dbt_build

"""Airflow DAG for the DOTA medallion pipeline.

Tasks wired as a DAG:

  refresh_constants -> load_bronze -> dbt_build -> [dbt_source_freshness, pg_dump_backup]

- refresh_constants / load_bronze / freshness / backup shell out to the shared
  `scripts/run_pipeline.py` so the pipeline logic is defined once.
- dbt_build is a first-class dbt-cosmos `DbtBuildOperator` (native `dbt build`,
  single task, using the committed `profiles.yml`).

The backup step streams pg_dump out of the running `dota_postgres` container
(--backup-docker) because the orchestrator image does not ship a pg_dump
binary. `backups/` is a repo mount inside the container (/opt/dota/backups),
so the dump lands on the host like a manual `pg_dump`.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from cosmos import ProfileConfig, ProjectConfig
from cosmos.operators import DbtBuildOperator

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
    tags=["dota", "medallion", "dbt", "cosmos"],
) as dag:

    refresh_constants = BashOperator(
        task_id="refresh_constants",
        bash_command=(
            "python /opt/dota/scripts/run_pipeline.py --only-constants "
            "--data-dir {{ var.value.get('data_dir', 'sample_data') }}"
        ),
    )

    load_bronze = BashOperator(
        task_id="load_bronze",
        bash_command=(
            "python /opt/dota/scripts/run_pipeline.py --only-load "
            "--data-dir {{ var.value.get('data_dir', 'sample_data') }}"
        ),
    )

    dbt_build = DbtBuildOperator(
        task_id="dbt_build",
        profile_config=ProfileConfig(
            profile_name="transform",
            target_name="dev",
            profiles_yml_filepath="/opt/dota/profiles.yml",
        ),
        project_config=ProjectConfig(dbt_project_path="/opt/dota/transform"),
        install_deps=False,
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

    refresh_constants >> load_bronze >> dbt_build >> [dbt_source_freshness, pg_dump_backup]

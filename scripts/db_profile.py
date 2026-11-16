"""Apply a safe or full-build Postgres memory profile at runtime.

The Docker command line only fixes shared_buffers (it needs a restart). The
settings below are reloadable, so a full refresh can temporarily raise them
and the pipeline can always restore the safe default in a finally block.

Usage:
    python scripts/db_profile.py --profile default
    python scripts/db_profile.py --profile full
    python scripts/db_profile.py --profile show
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

PROFILES = {
    "default": {
        "work_mem": "64MB",
        "maintenance_work_mem": "256MB",
        "effective_cache_size": "3GB",
        "max_parallel_workers_per_gather": 2,
        "max_parallel_workers": 4,
        "parallel_setup_cost": 100,
        "min_parallel_table_scan_size": 0,
    },
    "full": {
        "work_mem": "128MB",
        "maintenance_work_mem": "512MB",
        "effective_cache_size": "4GB",
        "max_parallel_workers_per_gather": 3,
        "max_parallel_workers": 6,
        "parallel_setup_cost": 100,
        "min_parallel_table_scan_size": 0,
    },
}


def _connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set. Copy .env.example to .env first.")
    return psycopg.connect(url, autocommit=True)


def apply_profile(profile: str) -> dict[str, str]:
    """Apply one profile and return the observed Postgres settings."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    settings = PROFILES[profile]
    with _connect() as conn, conn.cursor() as cur:
        for name, value in settings.items():
            cur.execute(
                sql.SQL("ALTER SYSTEM SET {} = {}").format(
                    sql.Identifier(name), sql.Literal(value)
                )
            )
        cur.execute("select pg_reload_conf()")
        cur.execute("select pg_sleep(0.25)")
        cur.execute(
            "select name, current_setting(name) from pg_settings "
            "where name = any(%s) order by name",
            (list(settings),),
        )
        observed = {row[0]: row[1] for row in cur.fetchall()}
    return observed


def show_profile() -> dict[str, str]:
    names = [
        "shared_buffers",
        "work_mem",
        "maintenance_work_mem",
        "effective_cache_size",
        "max_parallel_workers_per_gather",
        "max_parallel_workers",
    ]
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "select name, current_setting(name) from pg_settings "
            "where name = any(%s) order by name",
            (names,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the Postgres memory profile.")
    parser.add_argument(
        "--profile",
        choices=["default", "full", "show"],
        default="show",
        help="profile to apply, or show the current settings",
    )
    args = parser.parse_args()

    if args.profile == "show":
        for name, value in show_profile().items():
            print(f"{name:35} {value}")
        return

    observed = apply_profile(args.profile)
    print(f"applied Postgres profile: {args.profile}")
    for name, value in observed.items():
        print(f"{name:35} {value}")


if __name__ == "__main__":
    try:
        main()
    except psycopg.Error as exc:
        print(f"database error: {exc}", file=sys.stderr)
        raise SystemExit(1)

"""Build a small, portfolio-sized demo database from a curated match subset.

Default: 1,500 matches in the `dota_demo` database. This avoids loading the
full 29k-match scrape, which is too heavy for a 16GB laptop and adds no value
to an entry-level portfolio.

Usage:
    python scripts/demo_pipeline.py                 # recreate dota_demo + build
    python scripts/demo_pipeline.py --matches 800   # smaller/faster
    python scripts/demo_pipeline.py --keep          # keep existing demo DB
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv
from psycopg import sql

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")
PYTHON = sys.executable


def url_for(db: str) -> str:
    base = os.environ.get("DATABASE_URL")
    if not base:
        raise SystemExit("DATABASE_URL not set. Copy .env.example to .env first.")
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db}", parts.query, parts.fragment))


def ensure_demo_db(recreate: bool) -> None:
    admin = url_for("postgres")
    with psycopg.connect(admin, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("select 1 from pg_database where datname = 'dota_demo'")
        exists = cur.fetchone() is not None
        if exists and recreate:
            print("dropping existing dota_demo...")
            cur.execute("drop database dota_demo with (force)")
            exists = False
        if not exists:
            print("creating dota_demo...")
            cur.execute(sql.SQL("create database {}").format(sql.Identifier("dota_demo")))

    with psycopg.connect(url_for("dota_demo"), autocommit=True) as conn:
        for name in ("01_schemas.sql", "02_bronze_tables.sql"):
            path = BASE / "db" / "init" / name
            print(f"applying {path.name}...")
            conn.execute(path.read_text(encoding="utf-8"))


def make_demo_data(matches: int) -> None:
    target = BASE / "demo_data"
    if (target / "proMatches").exists() and len(list((target / "proMatches").glob("*.json"))) >= matches:
        print(f"using existing demo_data ({len(list((target / 'proMatches').glob('*.json')))} matches)")
        return
    print(f"building demo_data with {matches} matches...")
    subprocess.run(
        [PYTHON, str(BASE / "scripts" / "make_sample.py"),
         "--source", "data", "--target", "demo_data", "--matches", str(matches)],
        cwd=str(BASE), check=True,
    )


def build_demo(matches: int, recreate: bool) -> int:
    make_demo_data(matches)
    ensure_demo_db(recreate)
    env = os.environ.copy()
    env["POSTGRES_DB"] = "dota_demo"
    env["DATABASE_URL"] = url_for("dota_demo")
    env["DBT_THREADS"] = "2"
    print("loading demo data and building dbt models...")
    return subprocess.run(
        [PYTHON, str(BASE / "scripts" / "run_pipeline.py"),
         "--data-dir", "demo_data", "--full-refresh",
         "--db-profile", "default", "--threads", "2"],
        cwd=str(BASE), env=env,
    ).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the small portfolio demo database.")
    parser.add_argument("--matches", type=int, default=1500)
    parser.add_argument("--keep", action="store_true", help="do not drop/recreate dota_demo")
    parser.add_argument("--switch-powerbi", action="store_true",
                        help="point the PBIP semantic model at dota_demo after the build")
    args = parser.parse_args()

    rc = build_demo(args.matches, recreate=not args.keep)
    if rc != 0:
        raise SystemExit(rc)
    if args.switch_powerbi:
        subprocess.run(
            [PYTHON, str(BASE / "scripts" / "switch_powerbi_db.py"), "--database", "dota_demo"],
            cwd=str(BASE), check=True,
        )
    print("\ndemo database ready: dota_demo")
    print("Power BI target: run scripts/switch_powerbi_db.py --database dota_demo")


if __name__ == "__main__":
    main()

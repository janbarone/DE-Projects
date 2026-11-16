r"""Interactive command-line UI for the DOTA pipeline.

Run from the repo root with:  dota.cmd
or directly:  .venv\Scripts\python.exe scripts\dota_cli.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
DBT = ROOT / ".venv" / "Scripts" / "dbt.exe"
DATA_DIR = os.environ.get("DOTA_DATA_DIR", "data")

MENU = """
================================================================
   DOTA 2 Pipeline - Control Panel
   {root}
----------------------------------------------------------------
   [1]  Incremental update    load new files + dbt build
   [2]  Full rebuild demo     dota_demo --full-refresh (auto profile)
   [3]  Scrape live matches   OpenDota -> data/ (quota-aware)
   [4]  Active refresh        constants + load + build + backup
   [5]  dbt tests only
   [6]  Backup database       pg_dump -> backups/
   [7]  Start Postgres
   [8]  Stop Postgres
   [9]  Status                DB counts, freshness, memory profile
   [10] Postgres memory       show / default / full
   [11] Safe cleanup          caches + old backups
   [12] Refresh constants     heroes / items / abilities
   [13] Open Power BI report
   [14] Spark smoke test      M0 local PySpark check
   [15] Portfolio demo build  custom-size dota_demo (safe/fast)
   [16] Power BI DB target    switch dota_demo / dota
   [0]  Exit
================================================================
""".format(root=ROOT)


def _python() -> str:
    return str(PY) if PY.exists() else sys.executable


def _dbt() -> str:
    return str(DBT) if DBT.exists() else "dbt"


def run(cmd: list[str], cwd: Path = ROOT) -> int:
    print("\n$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        print(f"\n[FAILED] exit code {result.returncode}")
    return result.returncode


def pause() -> None:
    try:
        input("\nPress Enter to return to the menu...")
    except (EOFError, KeyboardInterrupt):
        pass


def ask(text: str, default: str) -> str:
    try:
        value = input(f"{text} [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return value or default


def confirm(text: str) -> bool:
    try:
        return input(f"{text} Type YES to continue: ").strip() == "YES"
    except (EOFError, KeyboardInterrupt):
        return False


def active_db() -> str:
    return os.environ.get("DOTA_ACTIVE_DB", "dota_demo")


def db_env(db: str) -> dict:
    env = os.environ.copy()
    base = env.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dota")
    parts = urlsplit(base)
    env["POSTGRES_DB"] = db
    env["DATABASE_URL"] = urlunsplit((parts.scheme, parts.netloc, f"/{db}", parts.query, parts.fragment))
    return env


def pipeline(*args: str, db: str | None = None) -> int:
    db = db or active_db()
    return run([_python(), str(ROOT / "scripts" / "run_pipeline.py"), *args], env=db_env(db))


def active_data_dir() -> str:
    return "demo_data" if active_db() == "dota_demo" else "data"


def scrape() -> int:
    mode = ask("Mode (promatches/leagues/full)", "promatches")
    limit = ask("Max matches (0 = no limit)", "50")
    cmd = [_python(), str(ROOT / "data" / "_fetch_matches.py"), "--mode", mode]
    if limit != "0":
        cmd.extend(["--limit", limit])
    return run(cmd)


def dbt_test() -> int:
    run([_python(), str(ROOT / "scripts" / "db_profile.py"), "--profile", "default"])
    return run([
        _dbt(), "test", "--profiles-dir", ".", "--project-dir", "transform",
        "--threads", os.environ.get("DBT_THREADS", "2"),
    ])


def docker(*args: str) -> int:
    return run(["docker", "compose", *args])


def choose_memory_profile() -> int:
    choice = ask("Profile (show/default/full)", "show")
    return run([_python(), str(ROOT / "scripts" / "db_profile.py"), "--profile", choice])


def show_status() -> int:
    """Print DB counts, freshness, and the active memory profile."""
    try:
        import psycopg
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        url = os.environ.get("DATABASE_URL")
        if not url:
            print("DATABASE_URL is not set.")
            return 1
        db = os.environ.get("DOTA_ACTIVE_DB", "dota_demo")
        parts = urlsplit(url)
        url = urlunsplit((parts.scheme, parts.netloc, f"/{db}", parts.query, parts.fragment))
        print(f"active database: {db}")
        with psycopg.connect(url, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("select pg_size_pretty(pg_database_size(%s))", (db,))
            print(f"database size: {cur.fetchone()[0]}")
            for table in ("bronze.matches", "silver.stg_matches", "gold.fact_matches"):
                cur.execute(f"select count(*) from {table}")
                print(f"{table:28} {cur.fetchone()[0]:,}")
            cur.execute("select max(source_fetched_at) from bronze.matches")
            print(f"latest source fetch: {cur.fetchone()[0]}")
            cur.execute("select pg_size_pretty(pg_total_relation_size('gold.fact_matches'))")
            print(f"gold.fact_matches size: {cur.fetchone()[0]}")
    except Exception as exc:
        print(f"database not reachable: {exc}")
        return 1

    run([_python(), str(ROOT / "scripts" / "db_profile.py"), "--profile", "show"])
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", "dota_postgres"],
        capture_output=True, text=True,
    )
    print(f"postgres container: {result.stdout.strip() or 'not running'}")
    return 0


def cleanup() -> int:
    script = ROOT / "scripts" / "cleanup.py"
    if not script.exists():
        print("cleanup.py not found.")
        return 1
    return run([_python(), str(script), "--interactive"])


def open_power_bi() -> int:
    report = ROOT / ".pbip" / "dota pipeline.pbip"
    if not report.exists():
        print(f"report not found: {report}")
        return 1
    os.startfile(str(report))  # type: ignore[attr-defined]
    print(f"opened: {report}")
    return 0


def demo_rebuild() -> int:
    matches = ask("Matches for the demo", "1500")
    if not confirm(f"Recreate dota_demo with {matches} matches and point Power BI at it?"):
        return 0
    return run([
        _python(), str(ROOT / "scripts" / "demo_pipeline.py"),
        "--matches", matches, "--switch-powerbi",
    ])


def switch_pbi_db() -> int:
    db = ask("Database target (dota_demo/dota)", "dota_demo")
    return run([_python(), str(ROOT / "scripts" / "switch_powerbi_db.py"), "--database", db])


def spark_smoke() -> int:
    compose = ROOT / "docker-compose.spark.yml"
    if not compose.exists():
        print("docker-compose.spark.yml not found.")
        return 1
    return run([
        "docker", "compose", "-f", str(compose), "run", "--rm", "spark",
        "/opt/spark/bin/spark-submit", "--master", "local[2]",
        "--driver-memory", "512m",
        "--conf", "spark.jars.ivy=/tmp/.ivy2",
        "--packages", "org.postgresql:postgresql:42.7.4",
        "/opt/spark/smoke/smoke.py",
    ])


def main() -> None:
    while True:
        print(MENU)
        try:
            choice = input("Choose: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if choice in ("0", "exit", "q", "quit"):
            print("Goodbye.")
            return
        elif choice == "1":
            pipeline("--data-dir", active_data_dir())
        elif choice == "2":
            if confirm("Full rebuild of the demo database (safe, ~14 min)?"):
                demo_rebuild()
        elif choice == "3":
            scrape()
        elif choice == "4":
            if confirm("Run constants + load + dbt build + backup on the active dataset?"):
                pipeline("--data-dir", active_data_dir(), "--refresh-constants", "--backup")
        elif choice == "5":
            dbt_test()
        elif choice == "6":
            pipeline("--only-backup", "--backup-docker")
        elif choice == "7":
            docker("up", "-d", "postgres")
        elif choice == "8":
            docker("stop", "postgres")
        elif choice == "9":
            show_status()
        elif choice == "10":
            choose_memory_profile()
        elif choice == "11":
            cleanup()
        elif choice == "12":
            pipeline("--only-constants", "--data-dir", active_data_dir())
        elif choice == "13":
            open_power_bi()
        elif choice == "14":
            spark_smoke()
        elif choice == "15":
            demo_rebuild()
        elif choice == "16":
            switch_pbi_db()
        else:
            print("Invalid choice.")
            continue
        pause()


if __name__ == "__main__":
    main()

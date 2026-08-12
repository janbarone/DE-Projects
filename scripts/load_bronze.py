"""Load raw JSON files under a data directory into the PostgreSQL bronze layer.

Reads the connection string from DATABASE_URL in .env (see .env.example).
Upserts are idempotent and re-runnable: records already present by their
natural key are updated in place, new ones are inserted.

Table mapping (mirrors db/init/02_bronze_tables.sql):
  <data_dir>/proMatches/<id>.json      -> bronze.matches   (one row per match file)
  <data_dir>/leagues/leagues.json      -> bronze.leagues   (per element, key leagueid)
  <data_dir>/proPlayers/proPlayers.json -> bronze.players   (per element, key account_id)
  <data_dir>/teams/teams.json          -> bronze.teams     (per element, key team_id)
  <data_dir>/heroStats/heroStats.json  -> bronze.hero_stats (per element, key id)
  <data_dir>/constants/<res>.json      -> bronze.constants (one row per resource)

Usage:
    python scripts/load_bronze.py                       # load from data/
    python scripts/load_bronze.py --data-dir sample_data  # load the committed demo set
"""
import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "data"))

from dota_common import get_logger  # noqa: E402

load_dotenv(BASE / ".env")

logger = get_logger("dota.load_bronze")

# (relative_glob, table, key_column, one_row_per_file)
MAP = [
    (Path("proMatches") / "*.json",        "bronze.matches",     "match_id",  True),
    (Path("leagues") / "leagues.json",     "bronze.leagues",     "leagueid",  False),
    (Path("proPlayers") / "proPlayers.json", "bronze.players",   "account_id", False),
    (Path("teams") / "teams.json",         "bronze.teams",       "team_id",   False),
    (Path("heroStats") / "heroStats.json", "bronze.hero_stats",  "id",        False),
    (Path("constants") / "*.json",         "bronze.constants",   "resource",  True),
]

UPSERT_SQL = (
    "INSERT INTO {table} ({key}, payload) VALUES (%s, %s) "
    "ON CONFLICT ({key}) DO UPDATE SET payload = EXCLUDED.payload, "
    "loaded_at = now()"
)


def load_json(path: Path):
    """Read a JSON file as UTF-8 and return parsed object."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_group(cur, conn, pattern: Path, table, key, one_per_file, commit_every=200):
    """Upsert every matching file into the given bronze table. Returns record count."""
    count = 0
    files = sorted(pattern.parent.glob(pattern.name))
    if not files:
        logger.warning("no files for pattern=%s table=%s", pattern, table)
        return 0

    upsert_sql = UPSERT_SQL.format(table=table, key=key)
    for i, f in enumerate(files, 1):
        data = load_json(f)
        if one_per_file:
            # One raw doc per file -> payload is the whole file value (dict or
            # list). Matches keep their match_id from the payload; the rest use
            # the file stem as the resource key.
            if isinstance(data, dict) and key in data:
                key_val = data[key]
                payload = {k: v for k, v in data.items() if k != "timestamp_fetched"}
            else:
                key_val = f.stem
                payload = data
            cur.execute(upsert_sql, (key_val, Jsonb(payload)))
            count += 1
        else:
            rows = data if isinstance(data, list) else [data]
            for rec in rows:
                if not isinstance(rec, dict) or key not in rec:
                    continue
                payload = {k: v for k, v in rec.items() if k != "timestamp_fetched"}
                cur.execute(upsert_sql, (rec[key], Jsonb(payload)))
                count += 1
        if one_per_file and i % commit_every == 0:
            conn.commit()  # commit periodically so large groups don't roll back
    logger.info("loaded table=%s rows=%s files=%s", table, count, len(files))
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Load raw JSON into the PostgreSQL bronze layer.")
    parser.add_argument(
        "--data-dir",
        default=str(BASE / "data"),
        help="Directory holding the raw JSON files (default: data/). "
             "Use sample_data/ for the committed reproducible demo set.",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL not set. Copy .env.example to .env and adjust, then re-run."
        )

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"data dir does not exist: {data_dir}")

    logger.info("loading bronze from %s", data_dir)
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        totals = {}
        for subpath, table, key, one_per_file in MAP:
            pattern = data_dir / subpath
            totals[table] = load_group(cur, conn, pattern, table, key, one_per_file)
            conn.commit()  # persist each group so partial runs don't roll back
        logger.info("bronze load complete totals=%s", totals)


if __name__ == "__main__":
    main()

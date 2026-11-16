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
from datetime import datetime, timezone
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
    "INSERT INTO {table} ({key}, payload, source_fetched_at) VALUES (%s, %s, %s) "
    "ON CONFLICT ({key}) DO UPDATE SET payload = EXCLUDED.payload, "
    "loaded_at = case when {table}.payload is distinct from EXCLUDED.payload "
    "then now() else {table}.loaded_at end, "
    "source_fetched_at = EXCLUDED.source_fetched_at"
)


def _parse_ts(value):
    """Parse an ISO-8601 timestamp from the payload, or return None."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _file_ts(path: Path):
    """Fallback source timestamp: the file's modification time in UTC."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def load_json(path: Path):
    """Read a JSON file as UTF-8 and return parsed object."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_group(cur, conn, pattern: Path, table, key, one_per_file,
               skip_existing=None, commit_every=200):
    """Upsert every matching file into the given bronze table. Returns record count.

    When `skip_existing` is a set of keys already present, files whose key is in
    that set are skipped without reading them (fast repeat loads). Pass
    `--refresh-existing` to disable this and propagate source corrections.
    A single unreadable file is logged and skipped instead of aborting the group.
    """
    count = 0
    skipped = 0
    failed = 0
    files = sorted(pattern.parent.glob(pattern.name))
    if not files:
        logger.warning("no files for pattern=%s table=%s", pattern, table)
        return 0

    total = len(files)
    upsert_sql = UPSERT_SQL.format(table=table, key=key)
    for i, f in enumerate(files, 1):
        if i % 500 == 0 or i == total:
            logger.info("progress table=%s processed=%s/%s inserted=%s skipped=%s failed=%s",
                        table, i, total, count, skipped, failed)
        if skip_existing is not None:
            try:
                if int(f.stem) in skip_existing:
                    skipped += 1
                    continue
            except (TypeError, ValueError):
                pass
        try:
            data = load_json(f)
        except Exception as exc:
            failed += 1
            logger.error("bad json file=%s table=%s error=%s", f, table, exc)
            continue

        file_ts = _file_ts(f)
        if one_per_file:
            # One raw doc per file -> payload is the whole file value (dict or
            # list). Matches keep their match_id from the payload; the rest use
            # the file stem as the resource key.
            if isinstance(data, dict) and key in data:
                key_val = data[key]
                source_ts = _parse_ts(data.get("timestamp_fetched")) or file_ts
                payload = {k: v for k, v in data.items() if k != "timestamp_fetched"}
            else:
                key_val = f.stem
                source_ts = file_ts
                payload = data
            try:
                cur.execute(upsert_sql, (key_val, Jsonb(payload), source_ts))
                count += 1
            except Exception as exc:
                failed += 1
                logger.error("upsert failed table=%s key=%s error=%s", table, key_val, exc)
                if hasattr(conn, "rollback"):
                    conn.rollback()
        else:
            rows = data if isinstance(data, list) else [data]
            for rec in rows:
                if not isinstance(rec, dict) or key not in rec:
                    continue
                source_ts = _parse_ts(rec.get("timestamp_fetched")) or file_ts
                payload = {k: v for k, v in rec.items() if k != "timestamp_fetched"}
                try:
                    cur.execute(upsert_sql, (rec[key], Jsonb(payload), source_ts))
                    count += 1
                except Exception as exc:
                    failed += 1
                    logger.error("upsert failed table=%s key=%s error=%s", table, rec[key], exc)
                    if hasattr(conn, "rollback"):
                        conn.rollback()
        if one_per_file and i % commit_every == 0:
            conn.commit()  # commit periodically so large groups don't roll back
    logger.info("loaded table=%s rows=%s files=%s skipped=%s failed=%s",
                table, count, total, skipped, failed)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Load raw JSON into the PostgreSQL bronze layer.")
    parser.add_argument(
        "--data-dir",
        default=str(BASE / "data"),
        help="Directory holding the raw JSON files (default: data/). "
             "Use sample_data/ for the committed reproducible demo set.",
    )
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="re-read existing match files too (slower) so source corrections reach bronze",
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
        # Snapshot existing match ids so already-loaded match files can be
        # skipped (matches are immutable, so this is safe and much faster).
        existing_matches = set()
        try:
            cur.execute("select match_id from bronze.matches")
            existing_matches = {int(row[0]) for row in cur.fetchall()}
        except Exception:
            existing_matches = set()
        logger.info("existing bronze matches=%s", len(existing_matches))
        # Older rows predate source_fetched_at; use loaded_at as a reasonable
        # approximation until the next scrape/load updates them.
        if not args.refresh_existing:
            for table in {row[1] for row in MAP}:
                try:
                    cur.execute(f"update {table} set source_fetched_at = loaded_at "
                                "where source_fetched_at is null")
                except Exception as exc:
                    logger.warning("source timestamp backfill skipped table=%s error=%s", table, exc)
            conn.commit()

        totals = {}
        for subpath, table, key, one_per_file in MAP:
            pattern = data_dir / subpath
            skip = existing_matches if table == "bronze.matches" and not args.refresh_existing else None
            totals[table] = load_group(cur, conn, pattern, table, key,
                                       one_per_file, skip)
            conn.commit()  # persist each group so partial runs don't roll back
        logger.info("bronze load complete totals=%s", totals)


if __name__ == "__main__":
    main()

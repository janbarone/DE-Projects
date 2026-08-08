"""LEAGUE MATCH FETCHER: discovers match_ids for a list of leagues via
/leagues/{id}/matchIds, then fetches the FULL raw match detail for each new
match_id and saves one file per match (same layout as _fetch_matches.py):

    proMatches/<match_id>.json          (complete /matches/{match_id} response + timestamp_fetched)

The league match_ids list is used only for discovery - it is NOT stored.

Resumable by design: any match already present in proMatches/ is skipped on
the next run, so you can stop (Ctrl+C) / pause / continue freely.

Quota: remaining API calls are printed after each run (per minute / per day).
The run stops automatically if the daily quota drops below the safety margin.

Usage:
    python _fetch_league_matches.py                # all default leagues, all missing matches
    python _fetch_league_matches.py --limit 10     # sample: 10 matches per run
    python _fetch_league_matches.py --league 600   # single league
    python _fetch_league_matches.py --leagues "600,2733"  # specific leagues
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dota_common import (  # noqa: E402
    BASE,
    DATA_DIR,
    http_get,
    print_quota,
    quota_remaining,
    timestamp_fetched,
    wait_exit,
    write_json,
)

DEFAULT_LEAGUES = [
    16899, 11625, 65001, 65006, 600, 2733, 4664, 5401, 9870,
    10749, 13256, 14268, 15728, 16935, 18324, 19719,
]

MAX_ATTEMPTS = 2  # enough tries per match; skip if still failing
DAY_STOP_AT = 50  # stop if remaining daily quota is below this
LOG_FILE = DATA_DIR / "_league_matches_log.txt"


class QuotaStop(Exception):
    """Raised when the daily API quota is nearly exhausted."""


def log(msg: str) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp_fetched()}  {msg}\n")


def fetch_match(mid: int, ts: str) -> dict:
    """Fetch one match with up to MAX_ATTEMPTS tries. Raises on failure."""
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = http_get(f"{BASE}/matches/{mid}")
            o = json.loads(raw)
            if not isinstance(o, dict) or not o.get("match_id"):
                raise ValueError("response has no match data")
            return o
        except Exception as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                print(f"    attempt {attempt} failed ({e}); retrying...")
                time.sleep(2)
    raise last_err


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch full matches for given leagues (append-only).")
    parser.add_argument("--league", type=int, default=None, help="single league id")
    parser.add_argument("--leagues", default=None, help="comma-separated league ids")
    parser.add_argument("--limit", type=int, default=None, help="max matches to fetch this run (None = all)")
    args = parser.parse_args()

    if args.league is not None:
        league_ids = [args.league]
    elif args.leagues:
        league_ids = [int(x) for x in args.leagues.replace(" ", "").split(",") if x]
    else:
        league_ids = list(DEFAULT_LEAGUES)

    ts = timestamp_fetched()
    saved = 0
    already = 0
    failures = []
    limit_left = args.limit  # None = unlimited
    quota_stopped = False

    try:
        for lid in league_ids:
            # --- discovery: match_ids for this league ---
            try:
                mids = json.loads(http_get(f"{BASE}/leagues/{lid}/matchIds"))
            except Exception as e:
                msg = f"league {lid}: discovery ERROR: {e}"
                print(f"  {msg}")
                log(f"FAIL {msg}")
                failures.append(f"league {lid} (discovery)")
                continue
            if not isinstance(mids, list) or not mids:
                print(f"league {lid}: no match ids")
                log(f"INFO league {lid}: no match ids")
                continue

            missing = [
                m for m in mids
                if not (DATA_DIR / "proMatches" / f"{m}.json").exists()
            ]
            league_skipped = len(mids) - len(missing)
            already += league_skipped

            if args.limit is not None and limit_left is not None:
                missing = missing[: max(limit_left, 0)]
            print(f"league {lid}: {len(missing)} to fetch, {league_skipped} already present")

            for mid in missing:
                q = quota_remaining()
                if q["day"] is not None and int(q["day"]) <= DAY_STOP_AT:
                    raise QuotaStop(q["day"])
                try:
                    o = fetch_match(mid, ts)
                    o["timestamp_fetched"] = ts
                    write_json(DATA_DIR / "proMatches" / f"{mid}.json", o)
                    saved += 1
                    if args.limit is not None:
                        if limit_left is not None:
                            limit_left -= 1
                        if limit_left is not None and limit_left <= 0:
                            break
                    print(f"  match {mid} saved ({saved})")
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    msg = f"match {mid} ERROR after {MAX_ATTEMPTS} tries: {e}"
                    print(f"  {msg}")
                    log(f"FAIL {msg}")
                    failures.append(mid)
    except QuotaStop as e:
        print(f"\nstopping: daily quota almost used up ({e} remaining)")
        log(f"INFO daily quota low ({e}) - run stopped early")
        quota_stopped = True
    except KeyboardInterrupt:
        print("\nstopped by user. Already-downloaded matches are skipped on the next run "
              "(re-run the same command to continue).")

    print(f"\ndone: saved {saved}, already present {already}, failed {len(failures)}")
    print_quota()
    q = quota_remaining()
    log(f"SUMMARY leagues={len(league_ids)} saved={saved} already={already} failed={len(failures)} "
        f"quota_minute={q['minute']} quota_day={q['day']}")
    if failures:
        print(f"failed/skipped: {failures}")
    if quota_stopped:
        wait_exit("Daily API quota reached - you can re-run the same command after the "
                  "daily quota resets to continue.")


if __name__ == "__main__":
    main()

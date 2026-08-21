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
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dota_common import (  # noqa: E402
    BASE,
    DATA_DIR,
    RateLimitedError,
    discover_league,
    have_match,
    http_get,
    is_drained,
    is_stale_error,
    mark_drained,
    mark_match_skipped,
    print_quota,
    quota_remaining,
    timestamp_fetched,
    wait_exit,
    write_json,
)

# The International leagues are auto-discovered by name ("The International
# YYYY"). OpenDota labels their tier inconsistently (old ones = "professional",
# newer = "premium"), so they are keyed off the name instead. A couple of ids
# the regex misses are pinned as extras:
#   11625 = "The International 10" (2-digit name, the COVID-delayed 2021 event)
#   16899 = generic "The International" catch-all
EXTRA_TI_LEAGUE_IDS = [16899, 11625]
TI_NAME_RE = re.compile(r"^The International (\d{4})$")


def load_leagues() -> list:
    """League records from /leagues, falling back to the local leagues.json."""
    try:
        recs = json.loads(http_get(f"{BASE}/leagues"))
        if isinstance(recs, list):
            return recs
    except Exception as e:
        print(f"  /leagues ERROR: {e}")
    path = DATA_DIR / "leagues" / "leagues.json"
    if path.exists():
        try:
            recs = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(recs, list):
                return recs
        except Exception as e:
            print(f"  leagues.json ERROR: {e}")
    return []


def discover_ti_league_ids(leagues) -> list:
    """The International league ids, chronological by year, plus any
    EXTRA_TI_LEAGUE_IDS the name regex misses (only those present in `leagues`)."""
    present = set()
    matched = []
    for r in leagues:
        if not isinstance(r, dict) or "leagueid" not in r:
            continue
        lid = int(r["leagueid"])
        present.add(lid)
        m = TI_NAME_RE.match(str(r.get("name", "")))
        if m:
            matched.append((int(m.group(1)), lid))
    matched.sort(key=lambda x: x[0])
    ids = [lid for _, lid in matched]
    for lid in EXTRA_TI_LEAGUE_IDS:
        if lid in present and lid not in ids:
            ids.append(lid)
    return ids

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
    parser.add_argument("--redrain", action="store_true",
                        help="ignore the drained-league registry and re-discover every league")
    args = parser.parse_args()

    if args.league is not None:
        league_ids = [args.league]
    elif args.leagues:
        league_ids = [int(x) for x in args.leagues.replace(" ", "").split(",") if x]
    else:
        league_ids = discover_ti_league_ids(load_leagues())

    ts = timestamp_fetched()
    saved = 0
    already = 0
    failures = []
    limit_left = args.limit  # None = unlimited
    quota_stopped = False

    try:
        for lid in league_ids:
            # --- local skip: league already fully drained on a previous run ---
            if not args.redrain and is_drained(lid):
                print(f"league {lid}: already drained, skipping discovery")
                continue
            # --- quota guard before spending a discovery call ---
            q0 = quota_remaining()
            if q0["day"] is not None and int(q0["day"]) <= DAY_STOP_AT:
                raise QuotaStop(q0["day"])
            # --- discovery: match_ids for this league ---
            mids, status, detail = discover_league(lid)
            if status == "rate_limited":
                raise QuotaStop("rate limited (daily quota likely spent)")
            if status in ("empty", "unavailable"):
                mark_drained(lid)
                msg = f"league {lid}: {detail}; skipping permanently"
                print(f"  {msg}")
                log(f"{'FAIL' if status == 'unavailable' else 'INFO'} {msg}")
                continue

            missing = [m for m in mids if not have_match(m)]
            league_skipped = len(mids) - len(missing)
            already += league_skipped

            if args.limit is not None and limit_left is not None:
                missing = missing[: max(limit_left, 0)]
            print(f"league {lid}: {len(missing)} to fetch, {league_skipped} already present")
            if not missing:
                mark_drained(lid)

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
                except RateLimitedError as e:
                    raise QuotaStop("rate limited (daily quota likely spent)") from e
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    if is_stale_error(e):
                        mark_match_skipped(mid)
                        msg = f"match {mid} unavailable; skipped permanently"
                        print(f"  {msg}")
                        log(f"INFO {msg}")
                    else:
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

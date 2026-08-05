"""MAIN MATCH FETCHER: one scraper that downloads every match, in two phases.

  Phase 1 - League priority. For EVERY league in the /leagues list, discover its
            match_ids via /leagues/{id}/matchIds and download EVERY missing
            match. Leagues are processed one at a time, so each league is fully
            drained before the next starts. Each match is retried
            (MAX_ATTEMPTS), progress/failures are logged to
            _league_matches_log.txt, and the run stops if the daily quota drops
            below the safety margin (DAY_STOP_AT).
  Phase 2 - Pro scrape. Once every league is exhausted, keep polling /proMatches
            and download new matches indefinitely, until the daily quota is
            used up.

Phase control (draining ~10k leagues takes days/weeks, so you choose):
  --mode full         (default) phase 1 drains as long as the daily quota
                      allows; phase 2 runs only if phase 1 is fully exhausted.
  --mode leagues      never proceed to phase 2 - grind leagues exclusively.
  --mode promatches   skip phase 1 entirely and just scrape proMatches
                      (avoids re-discovering all leagues once they're drained).

One file is written per match:
    proMatches/<match_id>.json   (the complete /matches/{match_id} response + timestamp_fetched)

Resumable by design: any match already on disk is skipped on the next run.

Usage:
    python _fetch_matches.py                     # --mode full: ALL leagues drained, then proMatches
    python _fetch_matches.py --mode leagues      # only drain leagues (never proMatches)
    python _fetch_matches.py --mode promatches   # only scrape proMatches (no league discovery)
    python _fetch_matches.py --limit 5           # stop after 5 matches (skips phase 2)
    python _fetch_matches.py --leagues "600,2733"   # only these leagues, then proMatches
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _fetch_league_matches import (  # noqa: E402
    DAY_STOP_AT,
    MAX_ATTEMPTS,
    QuotaStop,
    fetch_match,
    log,
)
from dota_common import (  # noqa: E402
    BASE,
    DATA_DIR,
    http_get,
    print_quota,
    quota_remaining,
    timestamp_fetched,
    write_json,
)

POLL_SECONDS = 30        # how long to wait between /proMatches re-polls


def day_left() -> int | None:
    """Remaining daily quota as an int, or None if unknown."""
    q = quota_remaining().get("day")
    return int(q) if q is not None else None


def on_disk(mid: int) -> bool:
    return (DATA_DIR / "proMatches" / f"{mid}.json").exists()


def is_stale_error(exc: Exception) -> bool:
    """True for errors that mean the match no longer exists / is unreachable,
    so we should skip it rather than block."""
    text = str(exc).lower()
    return "404" in text or "430" in text or "not found" in text


def save_match(mid: int, ts: str) -> bool:
    """Fetch and save one match. Returns True if saved, False if it errored."""
    raw = http_get(f"{BASE}/matches/{mid}")
    o = json.loads(raw)
    o["timestamp_fetched"] = ts
    write_json(DATA_DIR / "proMatches" / f"{mid}.json", o)
    return True


def next_pro_mid(feed) -> int | None:
    """Pop the first match_id from a proMatches feed that is not yet on disk."""
    while feed:
        m = feed.pop(0)
        mid = int(m["match_id"])
        if not on_disk(mid):
            return mid
    return None


def refresh_pro_feed() -> list | None:
    try:
        feed = json.loads(http_get(f"{BASE}/proMatches"))
        return feed if isinstance(feed, list) else None
    except Exception as e:
        print(f"  proMatches feed ERROR: {e}")
        return None


def phase1_league_priority(league_ids, limit_left, ts, saved, limit) -> tuple:
    """Download every missing match for every league, one league at a time.

    Each league is fully drained before the next starts. Returns
    (saved, already, failures, limit_left)."""
    already = 0
    failures = []
    for lid in league_ids:
        if limit is not None and limit_left is not None and limit_left <= 0:
            break
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

        missing = [m for m in mids if not on_disk(m)]
        league_skipped = len(mids) - len(missing)
        already += league_skipped

        if limit is not None and limit_left is not None:
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
                if limit is not None:
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
    return saved, already, failures, limit_left


def all_league_ids() -> list:
    """Every league id from the /leagues endpoint (fresh), falling back to the
    local leagues.json copy if the call fails."""
    try:
        recs = json.loads(http_get(f"{BASE}/leagues"))
        ids = [int(r["leagueid"]) for r in recs
               if isinstance(r, dict) and "leagueid" in r]
        if ids:
            return ids
    except Exception as e:
        print(f"  /leagues ERROR: {e}")
    path = DATA_DIR / "leagues" / "leagues.json"
    if path.exists():
        recs = json.loads(path.read_text(encoding="utf-8"))
        return [int(r["leagueid"]) for r in recs
                if isinstance(r, dict) and "leagueid" in r]
    return []


def phase2_pro_scrape(limit, saved, ts) -> int:
    """Poll /proMatches and download new matches until quota is used up or --limit reached."""
    print("league queue drained; scraping proMatches for new matches (until quota runs out)...")
    while True:
        if limit is not None and saved >= limit:
            print(f"reached --limit {limit}")
            break
        if day_left() is not None and day_left() <= 0:
            print("daily quota exhausted; stopping")
            break

        feed = refresh_pro_feed()
        if feed is None:
            time.sleep(POLL_SECONDS)
            continue
        while feed:
            if limit is not None and saved >= limit:
                break
            dl = day_left()
            if dl is not None and dl <= 0:
                break
            mid = next_pro_mid(feed)
            if mid is None:
                break
            try:
                save_match(mid, ts)
                saved += 1
                print(f"  pro match {mid} saved ({saved})")
            except Exception as e:
                if is_stale_error(e):
                    print(f"  pro match {mid} unavailable, skipped ({e})")
                else:
                    print(f"  pro match {mid} ERROR: {e}")

        # Current feed fully drained. Wait, then re-poll for new matches.
        print(f"  nothing new in this feed; re-polling /proMatches in {POLL_SECONDS}s...")
        time.sleep(POLL_SECONDS)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download every league's matches first, then scrape proMatches "
                    "until the daily quota is used up.")
    parser.add_argument("--mode", default=None,
                        choices=["full", "leagues", "promatches"],
                        help="download mode: full = leagues first then proMatches (default), "
                             "leagues = drain league matches only, promatches = proMatches only")
    parser.add_argument("--limit", type=int,
                        help="stop after this many fetches; omit to drain leagues then scrape "
                             "until the daily quota is exhausted")
    parser.add_argument("--leagues", default=None,
                        help="league ids (comma-separated) to download; default = EVERY league from /leagues")
    parser.add_argument("--leagues-only", action="store_true",
                        help="(alias) same as --mode leagues")
    parser.add_argument("--promatches-only", action="store_true",
                        help="(alias) same as --mode promatches")
    args = parser.parse_args()

    # Resolve the mode (--mode wins over the boolean aliases; conflict = error).
    if args.leagues_only and args.promatches_only:
        parser.error("--leagues-only and --promatches-only are mutually exclusive")
    mode = args.mode or ("leagues" if args.leagues_only
                         else "promatches" if args.promatches_only
                         else "full")
    if args.mode and args.leagues_only and args.mode != "leagues":
        parser.error("--leagues-only conflicts with --mode %s" % args.mode)
    if args.mode and args.promatches_only and args.mode != "promatches":
        parser.error("--promatches-only conflicts with --mode %s" % args.mode)

    run_leagues = mode in ("full", "leagues")
    run_promatches = mode in ("full", "promatches")
    print(f"mode: {mode}")

    if run_leagues:
        if args.leagues:
            league_ids = [int(x) for x in args.leagues.replace(" ", "").split(",") if x]
        else:
            league_ids = all_league_ids()
            print(f"league list: {len(league_ids)} leagues to drain")
        if not league_ids:
            print("no league ids to fetch" + ("" if mode == "leagues"
                                              else "; continuing to proMatches scrape"))
    else:
        league_ids = []

    if day_left() is not None and day_left() <= 0:
        print("daily quota already exhausted; nothing to do")
        print_quota()
        return

    ts = timestamp_fetched()
    saved = 0
    already = 0
    failures = []
    limit_left = args.limit  # None = unlimited

    try:
        # ---- Phase 1: league priority (drain every league) ----------------
        if run_leagues and league_ids:
            saved, already, failures, limit_left = phase1_league_priority(
                league_ids, limit_left, ts, saved, args.limit)

        # ---- Phase 2: proMatches scrape ------------------------------------
        if not run_promatches:
            print(f"mode '{mode}': not scraping proMatches")
        elif args.limit is not None and limit_left is not None and limit_left <= 0:
            print(f"reached --limit {args.limit}; skipping proMatches scrape")
        elif day_left() is not None and day_left() <= 0:
            print("daily quota exhausted; skipping proMatches scrape")
        else:
            saved = phase2_pro_scrape(args.limit, saved, ts)

    except QuotaStop as e:
        print(f"\nstopping: daily quota almost used up ({e} remaining)")
        log(f"INFO daily quota low ({e}) - run stopped early")
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


if __name__ == "__main__":
    main()

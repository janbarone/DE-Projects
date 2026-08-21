"""MAIN MATCH FETCHER: one scraper that downloads every match, in two phases.

  Phase 1 - League priority. Leagues are drained in this order: the explicit
            The International ids first, then PREMIUM, then PROFESSIONAL (all
            other tiers are disregarded). For each, discover its match_ids via
            /leagues/{id}/matchIds and download EVERY missing match. Leagues are
            processed one at a time, so each league is fully drained before the
            next starts. Each match is retried (MAX_ATTEMPTS), progress/failures
            are logged to _league_matches_log.txt, and the run stops if the
            daily quota drops below the safety margin (DAY_STOP_AT).
  Phase 2 - Pro scrape. Once the priority leagues are exhausted, poll
            /proMatches for new matches with exponential backoff, stopping at
            the daily quota safety margin (DAY_STOP_AT) or after enough empty
            polls.

Phase control (draining ~2.7k priority leagues takes days/weeks, so you choose):
  --mode full         (default) phase 1 drains as long as the daily quota
                      allows; phase 2 runs only if phase 1 is fully exhausted.
  --mode leagues      never proceed to phase 2 - grind leagues exclusively.
  --mode promatches   skip phase 1 entirely and just scrape proMatches
                      (avoids re-discovering all leagues once they're drained).

One file is written per match:
    proMatches/<match_id>.json   (the complete /matches/{match_id} response + timestamp_fetched)

Resumable by design: any match already on disk is skipped on the next run.

Usage:
    python _fetch_matches.py                     # prompts for mode; premium+professional leagues drained, then proMatches
    python _fetch_matches.py --mode full         # non-interactive: leagues first, then proMatches
    python _fetch_matches.py --mode leagues      # non-interactive: only drain leagues
    python _fetch_matches.py --mode promatches   # non-interactive: only scrape proMatches
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
    TI_LEAGUE_IDS,
    QuotaStop,
    fetch_match,
    log,
)
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

# Phase-2 /proMatches polling: back off exponentially when nothing new, so an
# empty feed doesn't burn the daily quota. Stops after MAX_EMPTY_POLLS empty
# polls (no new pro matches today) and respects DAY_STOP_AT.
POLL_BASE_SECONDS = 30      # first wait after an empty poll
POLL_MAX_SECONDS = 600      # cap the backoff (10 minutes)
MAX_EMPTY_POLLS = 20        # stop phase 2 after this many consecutive empty polls


def day_left() -> int | None:
    """Remaining daily quota as an int, or None if unknown."""
    q = quota_remaining().get("day")
    return int(q) if q is not None else None


def save_match(mid: int, ts: str) -> bool:
    """Fetch and save one match. Returns True if saved, False if it errored."""
    raw = http_get(f"{BASE}/matches/{mid}")
    o = json.loads(raw)
    o["timestamp_fetched"] = ts
    write_json(DATA_DIR / "proMatches" / f"{mid}.json", o)
    return True


def next_pro_mid(feed) -> int | None:
    """Pop the first match_id from a proMatches feed that is not yet known."""
    while feed:
        m = feed.pop(0)
        mid = int(m["match_id"])
        if not have_match(mid):
            return mid
    return None


def refresh_pro_feed() -> list | None:
    try:
        feed = json.loads(http_get(f"{BASE}/proMatches"))
        return feed if isinstance(feed, list) else None
    except RateLimitedError:
        raise
    except Exception as e:
        print(f"  proMatches feed ERROR: {e}")
        return None


def phase1_league_priority(league_ids, limit_left, ts, saved, limit, redrain) -> tuple:
    """Download every missing match for every league, one league at a time.

    Leagues already fully drained (see dota_common.mark_drained) are skipped
    without an API call, unless --redrain forces a full re-scan. Each league is
    fully drained before the next starts. Returns
    (saved, already, failures, limit_left)."""
    already = 0
    failures = []
    for lid in league_ids:
        if limit is not None and limit_left is not None and limit_left <= 0:
            break
        # --- local skip: league already fully drained on a previous run ---
        if not redrain and is_drained(lid):
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

        if limit is not None and limit_left is not None:
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
                if limit is not None:
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
    return saved, already, failures, limit_left


# Priority tiers for phase 1, drained AFTER the explicit TI list. All other
# tiers (amateur / unknown / excluded) are disregarded.
PRIORITY_TIERS = ["premium", "professional"]


def all_league_ids() -> list:
    """League ids to drain from the /leagues endpoint (fresh), falling back to
    the local leagues.json copy if the call fails.

    Order: explicit TI_LEAGUE_IDS first, then premium, then professional.
    TIs are pinned explicitly because OpenDota labels them inconsistently
    (old TIs = "professional", newer ones = "premium")."""
    try:
        recs = json.loads(http_get(f"{BASE}/leagues"))
    except Exception as e:
        print(f"  /leagues ERROR: {e}")
        recs = None
    if not isinstance(recs, list) or not recs:
        path = DATA_DIR / "leagues" / "leagues.json"
        if path.exists():
            recs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(recs, list) or not recs:
        return []

    tier_by_id = {}
    for r in recs:
        if isinstance(r, dict) and "leagueid" in r:
            tier_by_id[int(r["leagueid"])] = r.get("tier")

    # 1) explicit TIs first (keep our pinned order; skip any no longer listed)
    ids = [lid for lid in TI_LEAGUE_IDS if lid in tier_by_id]
    seen = set(ids)

    # 2) then premium, 3) then professional (API order, de-duped against the TIs)
    for tier in PRIORITY_TIERS:
        for lid, t in tier_by_id.items():
            if t == tier and lid not in seen:
                ids.append(lid)
                seen.add(lid)
    return ids


def phase2_pro_scrape(limit, saved, ts) -> int:
    """Poll /proMatches and download new matches, quota-efficiently.

    Backs off exponentially when the feed has nothing new (so an empty feed
    doesn't burn the daily quota), stops after MAX_EMPTY_POLLS consecutive empty
    polls, and stops before the quota hits zero (DAY_STOP_AT safety margin)."""
    print("league queue drained; scraping proMatches for new matches...")
    empty_polls = 0
    while True:
        if limit is not None and saved >= limit:
            print(f"reached --limit {limit}")
            break
        if day_left() is not None and day_left() <= DAY_STOP_AT:
            print("daily quota almost used up; stopping phase 2")
            break

        feed = refresh_pro_feed()
        if feed is None:
            time.sleep(POLL_BASE_SECONDS)
            continue

        got_new = False
        while feed:
            if limit is not None and saved >= limit:
                break
            dl = day_left()
            if dl is not None and dl <= DAY_STOP_AT:
                break
            mid = next_pro_mid(feed)
            if mid is None:
                break
            try:
                save_match(mid, ts)
                saved += 1
                got_new = True
                print(f"  pro match {mid} saved ({saved})")
            except RateLimitedError as e:
                raise QuotaStop("rate limited (daily quota likely spent)") from e
            except Exception as e:
                if is_stale_error(e):
                    mark_match_skipped(mid)
                    print(f"  pro match {mid} unavailable, skipped permanently")
                else:
                    print(f"  pro match {mid} ERROR: {e}")

        # Re-check quota before deciding to keep polling (inner loop may have
        # broken out because the safety margin was hit).
        dl = day_left()
        if dl is not None and dl <= DAY_STOP_AT:
            break

        if got_new:
            empty_polls = 0
            continue

        empty_polls += 1
        if empty_polls >= MAX_EMPTY_POLLS:
            print(f"  no new pro matches after {empty_polls} polls; stopping phase 2")
            break
        wait = min(POLL_BASE_SECONDS * (2 ** (empty_polls - 1)), POLL_MAX_SECONDS)
        print(f"  nothing new; re-polling /proMatches in {wait}s...")
        time.sleep(wait)
    return saved


def prompt_mode(default: str = "full") -> str:
    """Ask the user to pick a download mode via a numbered menu.

    Falls back to `default` when stdin is closed (e.g. scheduled / non-interactive
    runs piping to /dev/null) so the script never hangs without a console.
    """
    print()
    print("=" * 60)
    print("  DOTA Match Fetcher  --  select download mode")
    print("=" * 60)
    print("  1. Full       - TI leagues first, then premium + professional, then proMatches")
    print("  2. Leagues    - drain TI + premium + professional leagues only (phase 1)")
    print("  3. ProMatches - scrape proMatches only (phase 2)")
    print("  0. Exit")
    print("=" * 60)
    while True:
        try:
            choice = input("  Choose [1-3]: ").strip().lower()
        except EOFError:
            print(f"  (no input available; using default mode '{default}')")
            return default
        except KeyboardInterrupt:
            print("\n  Cancelled by user.")
            raise SystemExit(0)
        if choice in ("1", "full", "f", ""):
            return "full"
        if choice in ("2", "leagues", "league", "l"):
            return "leagues"
        if choice in ("3", "promatches", "promatch", "pro", "p"):
            return "promatches"
        if choice in ("0", "exit", "q", "quit"):
            print("\n  Goodbye!\n")
            raise SystemExit(0)
        print("  [!] Invalid choice - enter 1, 2, or 3")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download TI, premium and professional league matches first, "
                    "then scrape proMatches until the daily quota is used up.")
    parser.add_argument("--mode", default=None,
                        choices=["full", "leagues", "promatches"],
                        help="download mode: full = leagues first then proMatches (default), "
                             "leagues = drain league matches only, promatches = proMatches only")
    parser.add_argument("--limit", type=int,
                        help="stop after this many fetches; omit to drain leagues then scrape "
                             "until the daily quota is exhausted")
    parser.add_argument("--leagues", default=None,
                        help="league ids (comma-separated) to download; default = TI list, "
                             "then premium, then professional")
    parser.add_argument("--redrain", action="store_true",
                        help="ignore the drained-league registry and re-discover every league")
    parser.add_argument("--leagues-only", action="store_true",
                        help="(alias) same as --mode leagues")
    parser.add_argument("--promatches-only", action="store_true",
                        help="(alias) same as --mode promatches")
    args = parser.parse_args()

    # Resolve the mode: --mode / aliases skip the prompt; otherwise ask the user
    # interactively (works from a console or the Scripts Manager stdin box).
    if args.leagues_only and args.promatches_only:
        parser.error("--leagues-only and --promatches-only are mutually exclusive")
    if args.mode:
        mode = args.mode
    elif args.leagues_only:
        mode = "leagues"
    elif args.promatches_only:
        mode = "promatches"
    else:
        mode = prompt_mode()
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
        wait_exit("Daily API quota reached - run cannot continue today.")
        return

    ts = timestamp_fetched()
    saved = 0
    already = 0
    failures = []
    limit_left = args.limit  # None = unlimited
    quota_stopped = False

    try:
        # ---- Phase 1: league priority (drain every league) ----------------
        if run_leagues and league_ids:
            saved, already, failures, limit_left = phase1_league_priority(
                league_ids, limit_left, ts, saved, args.limit, args.redrain)

        # ---- Phase 2: proMatches scrape ------------------------------------
        if not run_promatches:
            print(f"mode '{mode}': not scraping proMatches")
        elif args.limit is not None and limit_left is not None and limit_left <= 0:
            print(f"reached --limit {args.limit}; skipping proMatches scrape")
        elif day_left() is not None and day_left() <= 0:
            print("daily quota exhausted; skipping proMatches scrape")
            quota_stopped = True
        else:
            saved = phase2_pro_scrape(args.limit, saved, ts)
            if day_left() is not None and day_left() <= 0:
                quota_stopped = True

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

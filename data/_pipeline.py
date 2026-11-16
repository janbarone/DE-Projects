"""DAILY PIPELINE: leagues, proPlayers, teams, heroStats.

Append-only for slowly changing dimensions, replace-on-fetch for heroStats
(which is a time-varying aggregate, not a static list).

- Matches             -> run _fetch_matches.py
- Constants           -> run _fetch_constants.py occasionally (heroes live there)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dota_common import (  # noqa: E402
    BASE,
    DATA_DIR,
    http_get,
    load_json_array,
    print_quota,
    timestamp_fetched,
    update_array_file,
    write_json,
)


def main() -> None:
    ts = timestamp_fetched()
    log = []

    def log_msg(msg: str) -> None:
        log.append(msg)
        print(msg)

    try:
        # 1. leagues
        recs = load_json_array(http_get(f"{BASE}/leagues"))
        added = update_array_file(DATA_DIR / "leagues" / "leagues.json", recs, "leagueid", ts)
        log_msg(f"leagues   : +{len(added)}")

        # 2. proPlayers
        recs = load_json_array(http_get(f"{BASE}/proPlayers"))
        added = update_array_file(DATA_DIR / "proPlayers" / "proPlayers.json", recs, "account_id", ts)
        log_msg(f"proPlayers: +{len(added)}")

        # 3. teams (all pages)
        all_teams = []
        page = 0
        while True:
            print(f"teams     : fetching page {page}...")
            recs = load_json_array(http_get(f"{BASE}/teams?page={page}"))
            if not recs:
                break
            all_teams.extend(recs)
            if len(recs) < 1000:
                break
            page += 1
        added = update_array_file(DATA_DIR / "teams" / "teams.json", all_teams, "team_id", ts)
        log_msg(f"teams     : +{len(added)} (fetched {len(all_teams)} across {page + 1} page(s))")

        # 4. heroStats is a time-varying aggregate. Replace the snapshot instead
        # of de-duplicating by hero id, otherwise pro_pick/pro_win freeze forever.
        recs = load_json_array(http_get(f"{BASE}/heroStats"))
        for rec in recs:
            if isinstance(rec, dict):
                rec["timestamp_fetched"] = ts
        write_json(DATA_DIR / "heroStats" / "heroStats.json", recs)
        log_msg(f"heroStats : {len(recs)} snapshot rows")
    except Exception as exc:
        log_msg(f"ERROR: {exc}")
        raise
    finally:
        with open(DATA_DIR / "_pipeline_log.txt", "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")
        log_msg(f"=== daily pipeline complete at {ts} ===")
        print_quota()


if __name__ == "__main__":
    main()

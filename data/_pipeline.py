"""DAILY PIPELINE: leagues, proPlayers, teams, heroStats.
Append-only, no duplicates. Full raw payloads (bronze-ready).
- Matches             -> run _fetch_matches.py (single integrated scraper:
                         league matches first, then proMatches).
- Constants           -> run _fetch_constants.py occasionally (heroes live there).
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
)

ts = timestamp_fetched()
log = []


def log_msg(msg: str) -> None:
    log.append(msg)
    print(msg)


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
    recs = load_json_array(http_get(f"{BASE}/teams?page={page}"))
    if not recs:
        break
    all_teams.extend(recs)
    if len(recs) < 1000:
        break
    page += 1
added = update_array_file(DATA_DIR / "teams" / "teams.json", all_teams, "team_id", ts)
log_msg(f"teams     : +{len(added)} (fetched {len(all_teams)} across {page + 1} page(s))")

# 4. heroStats (single call, snapshot of aggregate hero win/pick rates)
recs = load_json_array(http_get(f"{BASE}/heroStats"))
added = update_array_file(DATA_DIR / "heroStats" / "heroStats.json", recs, "id", ts)
log_msg(f"heroStats : +{len(added)}")

with open(DATA_DIR / "_pipeline_log.txt", "a", encoding="utf-8") as f:
    f.write("\n".join(log) + "\n")
log_msg(f"=== daily pipeline complete at {ts} ===")
print_quota()

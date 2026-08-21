"""CONSTANTS FETCHER: static game data (heroes, items, abilities, etc.).
These rarely change - run occasionally, NOT daily.
Append-only with dedup by resource key. Use --force to re-fetch/overwrite all.

Usage:
    python _fetch_constants.py
    python _fetch_constants.py --force
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dota_common import (  # noqa: E402
    BASE,
    DATA_DIR,
    http_get,
    print_quota,
    timestamp_fetched,
    update_array_file,
    write_json,
)

RESOURCES = [
    "abilities", "ability_ids", "aghs_desc", "ancients", "chat_wheel", "cluster",
    "countries", "game_mode", "hero_abilities", "hero_lore", "heroes",
    "item_colors", "item_ids", "items", "lobby_type", "neutral_abilities",
    "order_types", "patch", "patchnotes", "permanent_buffs", "player_colors",
    "region", "skillshots", "xp_level",
]

CANDIDATE_KEYS = ["name", "id", "hero_id", "account_id", "match_id", "leagueid", "team_id"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OpenDota static constants (append-only).")
    parser.add_argument("--force", action="store_true", help="delete existing files and re-fetch everything")
    parser.add_argument(
        "--data-dir",
        default=str(DATA_DIR),
        help="directory to write constants into (default: the data/ dir this script lives in)",
    )
    args = parser.parse_args()

    constants_dir = Path(args.data_dir) / "constants"
    ts = timestamp_fetched()

    for resource in RESOURCES:
        file = constants_dir / f"{resource}.json"
        try:
            if args.force and file.exists():
                file.unlink()
            raw = http_get(f"{BASE}/constants/{resource}")
            parsed = json.loads(raw)

            if isinstance(parsed, list):
                recs = list(parsed)
                added = []
                for kf in CANDIDATE_KEYS:
                    added = update_array_file(file, recs, kf, ts)
                    if added:
                        break
                if added:
                    print(f"constants\\{resource} : +{len(added)}")
                elif not file.exists():
                    write_json(file, recs)
                    print(f"constants\\{resource} : stored raw ({len(recs)} items, no object key)")
                else:
                    print(f"constants\\{resource} : no new records")
            else:
                obj = {}
                keys = set()
                if file.exists():
                    obj = json.loads(file.read_text(encoding="utf-8"))
                    keys = set(obj.keys())
                added = 0
                for name, value in parsed.items():
                    if name in keys:
                        continue
                    keys.add(name)
                    if isinstance(value, dict):
                        value["timestamp_fetched"] = ts
                    obj[name] = value
                    added += 1
                if added:
                    write_json(file, obj)
                print(f"constants\\{resource} : +{added}")
        except Exception as e:
            print(f"constants\\{resource} : ERROR {e}")

    print("constants fetch complete")
    print_quota()


if __name__ == "__main__":
    main()

"""Curate a small, reproducible sample dataset for the DOTA pipeline.

Scans the live scrape directory (data/) and selects a fixed number of matches
that maximize coverage of every Power BI report page / visual / slicer, then
copies them (plus the full reference files) into a committed sample directory
(sample_data/) that a reviewer can load without re-scraping the API.

Coverage goals (mapped to report pages):
  - Overview / Matches   : matches, game_mode, lobby_type, region, patch, league
  - Hero Meta            : picks_bans + match_players (hero_id) + patch
  - Players / Teams      : account_id, team ids (incl. missing-team flags)
  - Draft                : picks_bans
  - Combat               : teamfights
  - Match Breakdown      : runes, kills_log, obs_log/sen_log, damage_inflictor_received
  - Progression/Economy  : per-minute gold_t/xp_t/lh_t/dn_t + purchase_log
  - Match Detail         : ability_upgrades_arr (skills/talents), items

Deterministic (no randomness): the same inputs produce the same sample.

Usage:
    python scripts/make_sample.py                     # data/ -> sample_data/, 200 matches
    python scripts/make_sample.py --matches 100 --dry-run
    python scripts/make_sample.py --source data --target sample_data
"""
import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "data"))

from dota_common import get_logger  # noqa: E402

logger = get_logger("dota.make_sample")

# Reference files copied wholesale (dims need the complete lookup set so the
# dbt relationship tests pass).
REFERENCE_PATHS = [
    Path("leagues") / "leagues.json",
    Path("proPlayers") / "proPlayers.json",
    Path("teams") / "teams.json",
    Path("heroStats") / "heroStats.json",
    Path("constants"),
]


def _non_empty_list(v) -> bool:
    return isinstance(v, list) and len(v) > 0


def _non_empty_dict(v) -> bool:
    return isinstance(v, dict) and len(v) > 0


def scan_match(path: Path) -> dict | None:
    """Parse one match file into a lightweight coverage dict (or None if unusable)."""
    try:
        o = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None

    players = o.get("players") or []
    flags = {
        "has_gold_t": any(_non_empty_list(p.get("gold_t")) for p in players if isinstance(p, dict)),
        "has_xp_t": any(_non_empty_list(p.get("xp_t")) for p in players if isinstance(p, dict)),
        "has_ability_upgrades": any(_non_empty_list(p.get("ability_upgrades_arr")) for p in players if isinstance(p, dict)),
        "has_purchase_log": any(_non_empty_list(p.get("purchase_log")) for p in players if isinstance(p, dict)),
        "has_obs_log": any(_non_empty_list(p.get("obs_log")) for p in players if isinstance(p, dict)),
        "has_sen_log": any(_non_empty_list(p.get("sen_log")) for p in players if isinstance(p, dict)),
        "has_damage_type": any(_non_empty_dict(p.get("damage_inflictor_received")) for p in players if isinstance(p, dict)),
        "has_runes": any(_non_empty_dict(p.get("runes")) for p in players if isinstance(p, dict)),
        "has_kills_log": any(_non_empty_list(p.get("kills_log")) for p in players if isinstance(p, dict)),
        "has_teamfights": _non_empty_list(o.get("teamfights")),
        "has_picks_bans": _non_empty_list(o.get("picks_bans")),
        "has_hero_zero": any(p.get("hero_id") in (0, "0") for p in players if isinstance(p, dict)),
    }
    radiant_team_id = o.get("radiant_team_id")
    dire_team_id = o.get("dire_team_id")
    flags["has_missing_team"] = not radiant_team_id or not dire_team_id

    richness = sum(1 for v in flags.values() if v)
    return {
        "path": path,
        "match_id": str(o.get("match_id", path.stem)),
        "radiant_win": o.get("radiant_win"),
        "leagueid": o.get("leagueid"),
        "start_time": o.get("start_time") or 0,
        "patch": o.get("patch"),
        "game_mode": o.get("game_mode"),
        "lobby_type": o.get("lobby_type"),
        "region": o.get("region"),
        "n_teamfights": len(o.get("teamfights") or []),
        "n_picks_bans": len(o.get("picks_bans") or []),
        "richness": richness,
        "flags": flags,
    }


def _best(candidates: list[dict], already: set, key=None) -> dict | None:
    pool = [m for m in candidates if m["path"] not in already]
    if not pool:
        return None
    return max(pool, key=key or (lambda m: (m["richness"], m["n_teamfights"], m["n_picks_bans"])))


def select_matches(meta: list[dict], n: int, focus_leagues: int = 12) -> list[dict]:
    """Greedy, deterministic selection maximizing coverage + league spread.

    League spread is focused on the top `focus_leagues` leagues (by match count)
    so the league/team slicers have enough matches per league to be meaningful,
    rather than 1 match across hundreds of leagues."""
    if n <= 0:
        return []

    selected: list[dict] = []
    chosen: set = set()

    # 1. Coverage passes: ensure every required branch has at least one match.
    required = [
        ("radiant_win True", lambda m: m["radiant_win"] is True),
        ("radiant_win False", lambda m: m["radiant_win"] is False),
        ("draw", lambda m: m["radiant_win"] is None),
        ("missing team", lambda m: m["flags"]["has_missing_team"]),
        ("hero_id=0", lambda m: m["flags"]["has_hero_zero"]),
        ("gold_t", lambda m: m["flags"]["has_gold_t"]),
        ("ability_upgrades", lambda m: m["flags"]["has_ability_upgrades"]),
        ("purchase_log", lambda m: m["flags"]["has_purchase_log"]),
        ("teamfights", lambda m: m["flags"]["has_teamfights"]),
        ("picks_bans", lambda m: m["flags"]["has_picks_bans"]),
        ("damage_type", lambda m: m["flags"]["has_damage_type"]),
        ("runes", lambda m: m["flags"]["has_runes"]),
        ("kills_log", lambda m: m["flags"]["has_kills_log"]),
        ("obs_log", lambda m: m["flags"]["has_obs_log"]),
    ]
    for label, pred in required:
        if len(selected) >= n:
            break
        pool = [m for m in meta if pred(m)]
        if not pool:
            logger.warning("coverage branch unavailable: %s", label)
            continue
        best = _best(pool, chosen)
        if best is not None:
            selected.append(best)
            chosen.add(best["path"])

    # 1b. Dimension diversity: ensure a spread of game_mode / lobby_type so the
    #     decode-dimension slicers are not a single value.
    for field in ("game_mode", "lobby_type"):
        vals = sorted(
            {m[field] for m in meta if m[field] is not None},
            key=lambda v: -sum(1 for m in meta if m[field] == v),
        )
        for v in vals[:5]:
            if len(selected) >= n:
                break
            best = _best([m for m in meta if m[field] == v], chosen)
            if best is not None:
                selected.append(best)
                chosen.add(best["path"])

    # 2. League spread: round-robin over the top leagues (most populated first)
    #    so several competitions are represented with enough matches each.
    if len(selected) < n:
        by_league = defaultdict(list)
        for m in meta:
            by_league[m["leagueid"]].append(m)
        leagues = sorted(by_league, key=lambda lid: -len(by_league[lid]))
        focus = leagues[:focus_leagues]
        while len(selected) < n:
            added = False
            for lid in focus:
                if len(selected) >= n:
                    break
                best = _best(by_league[lid], chosen)
                if best is not None:
                    selected.append(best)
                    chosen.add(best["path"])
                    added = True
            if not added:
                break

    # 3. Fill any remaining slots with the richest matches overall.
    if len(selected) < n:
        rest = sorted([m for m in meta if m["path"] not in chosen],
                      key=lambda m: (-m["richness"], -m["n_teamfights"], -m["n_picks_bans"]))
        for m in rest:
            if len(selected) >= n:
                break
            selected.append(m)
            chosen.add(m["path"])

    return selected


def coverage_report(selected: list[dict]) -> dict:
    flags = [
        "has_gold_t", "has_xp_t", "has_ability_upgrades", "has_purchase_log",
        "has_obs_log", "has_sen_log", "has_damage_type", "has_runes",
        "has_kills_log", "has_teamfights", "has_picks_bans", "has_hero_zero",
        "has_missing_team",
    ]
    out = {}
    for f in flags:
        out[f] = sum(1 for m in selected if m["flags"][f])
    out["matches"] = len(selected)
    out["radiant_wins"] = sum(1 for m in selected if m["radiant_win"] is True)
    out["dire_wins"] = sum(1 for m in selected if m["radiant_win"] is False)
    out["draws"] = sum(1 for m in selected if m["radiant_win"] is None)
    out["leagues"] = len({m["leagueid"] for m in selected})
    out["patches"] = len({m["patch"] for m in selected})
    out["regions"] = len({m["region"] for m in selected})
    out["game_modes"] = len({m["game_mode"] for m in selected})
    return out


def copy_reference(source: Path, target: Path) -> list[str]:
    copied = []
    for rel in REFERENCE_PATHS:
        src = source / rel
        dst = target / rel
        if not src.exists():
            logger.warning("reference path missing: %s", src)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            copied.extend(str(p.relative_to(source)) for p in src.glob("*.json"))
        else:
            shutil.copy2(src, dst)
            copied.append(str(rel))
    return copied


def main() -> None:
    ap = argparse.ArgumentParser(description="Curate a reproducible sample dataset.")
    ap.add_argument("--source", default=str(BASE / "data"))
    ap.add_argument("--target", default=str(BASE / "sample_data"))
    ap.add_argument("--matches", type=int, default=200)
    ap.add_argument("--leagues", type=int, default=12,
                    help="number of leagues to focus the spread on (default 12)")
    ap.add_argument("--dry-run", action="store_true", help="report only, do not copy")
    args = ap.parse_args()

    source = Path(args.source)
    target = Path(args.target)
    match_dir = source / "proMatches"
    if not match_dir.exists():
        raise SystemExit(f"no proMatches dir at {match_dir}")

    files = sorted(match_dir.glob("*.json"))
    logger.info("scanning %s match files...", len(files))
    meta = []
    for f in files:
        m = scan_match(f)
        if m is not None:
            meta.append(m)
    logger.info("parsed %s matches (%s unparseable)", len(meta), len(files) - len(meta))

    selected = select_matches(meta, args.matches, focus_leagues=args.leagues)
    report = coverage_report(selected)
    logger.info("selected %s matches", len(selected))

    print("\n=== sample coverage (selected / required) ===")
    for k in ("matches", "radiant_wins", "dire_wins", "draws", "leagues", "patches", "regions", "game_modes"):
        print(f"  {k:14} {report[k]}")
    for k, v in report.items():
        if k.startswith("has_"):
            print(f"  {k:14} {v}/{len(selected)}")

    if args.dry_run:
        print("\n(dry run - nothing copied)")
        return

    if target.exists():
        shutil.rmtree(target)
    (target / "proMatches").mkdir(parents=True, exist_ok=True)

    copied_matches = 0
    for m in selected:
        shutil.copy2(m["path"], target / "proMatches" / m["path"].name)
        copied_matches += 1

    copied_ref = copy_reference(source, target)

    manifest = {
        "description": "Curated reproducible sample for the DOTA pipeline (medallion demo).",
        "matches": len(selected),
        "coverage": report,
        "match_ids": [m["match_id"] for m in selected],
        "reference_files": copied_ref,
        "source": str(source),
    }
    (target / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info("copied matches=%s reference_files=%s to %s", copied_matches, len(copied_ref), target)
    print(f"\nDone. Sample written to {target} ({copied_matches} matches + {len(copied_ref)} reference files).")


if __name__ == "__main__":
    main()

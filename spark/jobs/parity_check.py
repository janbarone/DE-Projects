"""Compare local PySpark silver/gold Delta tables with dbt PostgreSQL tables."""
from common import DELTA_DIR, read_table, spark_session
from pyspark.sql import functions as F

spark = spark_session("dota-m1-parity")

CHECKS = {
    "silver/stg_matches": {
        "dbt": "silver.stg_matches",
        "keys": ["match_id"],
        "metrics": {
            "rows": F.count("*"),
            "duration": F.sum("duration_sec"),
            "radiant_score": F.sum("radiant_score"),
        },
    },
    "silver/stg_match_players": {
        "dbt": "silver.stg_match_players",
        "keys": ["match_id", "player_slot"],
        "metrics": {
            "rows": F.count("*"),
            "kills": F.sum("kills"),
            "deaths": F.sum("deaths"),
            "assists": F.sum("assists"),
        },
    },
    "silver/stg_picks_bans": {
        "dbt": "silver.stg_picks_bans",
        "keys": ["match_id", "order_no"],
        "metrics": {
            "rows": F.count("*"),
            "picks": F.sum(F.when(F.col("is_pick"), 1).otherwise(0)),
            "bans": F.sum(F.when(~F.col("is_pick"), 1).otherwise(0)),
        },
    },
    "silver/stg_heroes": {
        "dbt": "silver.stg_heroes",
        "keys": ["hero_id"],
        "metrics": {"rows": F.count("*")},
    },
    "silver/stg_hero_stats": {
        "dbt": "silver.stg_hero_stats",
        "keys": ["hero_id"],
        "metrics": {
            "rows": F.count("*"),
            "pro_pick": F.sum("pro_pick"),
            "pub_pick": F.sum("pub_pick"),
        },
    },
    "silver/stg_teams": {
        "dbt": "silver.stg_teams",
        "keys": ["team_id"],
        "metrics": {"rows": F.count("*")},
    },
    "gold/dim_hero": {
        "dbt": "gold.dim_hero",
        "keys": ["hero_id"],
        "metrics": {
            "rows": F.count("*"),
            "match_picks": F.sum("match_picks"),
            "draft_picks": F.sum("match_draft_picks"),
            "draft_bans": F.sum("match_draft_bans"),
        },
    },
    "gold/dim_team": {
        "dbt": "gold.dim_team",
        "keys": ["team_id"],
        "metrics": {
            "rows": F.count("*"),
            "appearances": F.sum("match_appearances"),
            "wins": F.sum("match_wins"),
        },
    },
    "gold/fact_matches": {
        "dbt": "gold.fact_matches",
        "keys": ["match_id"],
        "metrics": {
            "rows": F.count("*"),
            "radiant_score": F.sum("radiant_score"),
            "dire_score": F.sum("dire_score"),
        },
    },
    "gold/fact_match_players": {
        "dbt": "gold.fact_match_players",
        "keys": ["match_id", "player_slot"],
        "metrics": {
            "rows": F.count("*"),
            "kills": F.sum("kills"),
            "deaths": F.sum("deaths"),
            "assists": F.sum("assists"),
        },
    },
    "gold/fact_picks_bans": {
        "dbt": "gold.fact_picks_bans",
        "keys": ["match_id", "order_no"],
        "metrics": {
            "rows": F.count("*"),
            "picks": F.sum(F.when(F.col("is_pick"), 1).otherwise(0)),
            "bans": F.sum(F.when(~F.col("is_pick"), 1).otherwise(0)),
        },
    },
}


EXTRA_CHECKS = {
    "gold/dim_game_mode": {"dbt": "gold.dim_game_mode", "keys": ["game_mode_id"], "metrics": {"rows": F.count("*")}},
    "gold/dim_lobby_type": {"dbt": "gold.dim_lobby_type", "keys": ["lobby_type_id"], "metrics": {"rows": F.count("*")}},
    "gold/dim_region": {"dbt": "gold.dim_region", "keys": ["region_id"], "metrics": {"rows": F.count("*")}},
    "gold/dim_item": {"dbt": "gold.dim_item", "keys": ["item_id"], "metrics": {"rows": F.count("*")}},
    "gold/dim_patch": {"dbt": "gold.dim_patch", "keys": ["patch_id"], "metrics": {"rows": F.count("*")}},
    "gold/dim_league": {"dbt": "gold.dim_league", "keys": ["leagueid"], "metrics": {"rows": F.count("*")}},
    "gold/dim_hero_role": {"dbt": "gold.dim_hero_role", "keys": ["hero_id", "role"], "metrics": {"rows": F.count("*")}},
    "gold/dim_rune": {"dbt": "gold.dim_rune", "keys": ["rune_key"], "metrics": {"rows": F.count("*")}},
    "gold/dim_date": {"dbt": "gold.dim_date", "keys": ["date"], "metrics": {"rows": F.count("*")}},
    "gold/dim_player": {"dbt": "gold.dim_player", "keys": ["account_id"], "metrics": {"rows": F.count("*"), "picks": F.sum("match_picks")}},
    "gold/fact_team_matches": {"dbt": "gold.fact_team_matches", "keys": ["match_id", "side"], "metrics": {"rows": F.count("*")}},
    "gold/fact_hero_side": {"dbt": "gold.fact_hero_side", "keys": ["hero_id", "side"], "metrics": {"rows": F.count("*"), "picks": F.sum("hero_side_picks")}},
    "gold/fact_hero_matchups": {"dbt": "gold.fact_hero_matchups", "keys": ["match_id", "radiant_hero_id", "dire_hero_id"], "metrics": {"rows": F.count("*")}},
    "gold/fact_hero_matchup_stats": {"dbt": "gold.fact_hero_matchup_stats", "keys": ["matchup_label"], "metrics": {"rows": F.count("*"), "games": F.sum("matchup_games")}},
    "gold/fact_hero_matchups_hero": {"dbt": "gold.fact_hero_matchups_hero", "keys": ["match_id", "hero_id", "opponent_id"], "metrics": {"rows": F.count("*")}},
    "gold/fact_team_h2h": {"dbt": "gold.fact_team_h2h", "keys": ["match_id"], "metrics": {"rows": F.count("*")}},
    "gold/fact_draft_sequence": {"dbt": "gold.fact_draft_sequence", "keys": ["match_id", "slot"], "metrics": {"rows": F.count("*")}},
}
CHECKS.update(EXTRA_CHECKS)

failures = []
for label, config in CHECKS.items():
    delta = spark.read.format("delta").load(f"{DELTA_DIR}/{label}")
    dbt = read_table(spark, config["dbt"])
    print(f"\n== {label} ==")
    d_rows, g_rows = delta.count(), dbt.count()
    print(f"rows delta={d_rows} dbt={g_rows}")
    if d_rows != g_rows:
        failures.append(f"{label}: row count {d_rows} != {g_rows}")

    keys = config["keys"]
    missing = dbt.select(*keys).distinct().exceptAll(delta.select(*keys).distinct()).count()
    extra = delta.select(*keys).distinct().exceptAll(dbt.select(*keys).distinct()).count()
    print(f"key gap dbt_only={missing} delta_only={extra}")
    if missing or extra:
        failures.append(f"{label}: key gap dbt_only={missing} delta_only={extra}")

    for name, expr in config["metrics"].items():
        d_val = delta.agg(expr).first()[0]
        g_val = dbt.agg(expr).first()[0]
        print(f"{name:18} delta={d_val!r:>20} dbt={g_val!r:>20}")
        if d_val != g_val:
            failures.append(f"{label}.{name}: {d_val!r} != {g_val!r}")

print("\nPARITY", "FAILED" if failures else "PASSED")
for failure in failures:
    print(" -", failure)
raise SystemExit(1 if failures else 0)

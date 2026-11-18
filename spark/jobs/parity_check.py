"""Compare the local PySpark Delta gold tables with dbt's Postgres gold tables."""
from common import DELTA_DIR, read_table, spark_session
from pyspark.sql import functions as F

spark = spark_session("dota-m1-parity")

CHECKS = {
    "dim_hero": {
        "keys": ["hero_id"],
        "metrics": {
            "rows": F.count("*"),
            "match_picks": F.sum("match_picks"),
            "draft_picks": F.sum("match_draft_picks"),
            "draft_bans": F.sum("match_draft_bans"),
        },
    },
    "dim_team": {
        "keys": ["team_id"],
        "metrics": {
            "rows": F.count("*"),
            "appearances": F.sum("match_appearances"),
            "wins": F.sum("match_wins"),
        },
    },
    "fact_matches": {
        "keys": ["match_id"],
        "metrics": {
            "rows": F.count("*"),
            "radiant_score": F.sum("radiant_score"),
            "dire_score": F.sum("dire_score"),
        },
    },
    "fact_match_players": {
        "keys": ["match_id", "player_slot"],
        "metrics": {
            "rows": F.count("*"),
            "kills": F.sum("kills"),
            "deaths": F.sum("deaths"),
            "assists": F.sum("assists"),
        },
    },
    "fact_picks_bans": {
        "keys": ["match_id", "order_no"],
        "metrics": {
            "rows": F.count("*"),
            "picks": F.sum(F.when(F.col("is_pick"), 1).otherwise(0)),
            "bans": F.sum(F.when(~F.col("is_pick"), 1).otherwise(0)),
        },
    },
}

failures = []
for table, config in CHECKS.items():
    delta = spark.read.format("delta").load(f"{DELTA_DIR}/gold/{table}")
    dbt = read_table(spark, f"gold.{table}")
    print(f"\n== {table} ==")
    d_rows, g_rows = delta.count(), dbt.count()
    print(f"rows delta={d_rows} dbt={g_rows}")
    if d_rows != g_rows:
        failures.append(f"{table}: row count {d_rows} != {g_rows}")

    keys = config["keys"]
    missing = dbt.select(*keys).distinct().exceptAll(delta.select(*keys).distinct()).count()
    extra = delta.select(*keys).distinct().exceptAll(dbt.select(*keys).distinct()).count()
    print(f"key gap dbt_only={missing} delta_only={extra}")
    if missing or extra:
        failures.append(f"{table}: key gap dbt_only={missing} delta_only={extra}")

    for name, expr in config["metrics"].items():
        d_val = delta.agg(expr).first()[0]
        g_val = dbt.agg(expr).first()[0]
        print(f"{name:18} delta={d_val!r:>20} dbt={g_val!r:>20}")
        if d_val != g_val:
            failures.append(f"{table}.{name}: {d_val!r} != {g_val!r}")

print("\nPARITY", "FAILED" if failures else "PASSED")
for failure in failures:
    print(" -", failure)
raise SystemExit(1 if failures else 0)

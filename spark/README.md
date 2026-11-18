# Spark / PySpark (M0-M1)

## M0: smoke test

```powershell
docker compose up -d postgres
docker compose -f docker-compose.spark.yml run --rm spark \
  /opt/spark/bin/spark-submit --master local[2] \
  --driver-memory 512m --conf spark.jars.ivy=/tmp/.ivy2 \
  --packages org.postgresql:postgresql:42.7.4 \
  /opt/spark/smoke/smoke.py
```

It reads `bronze.matches` from `dota_demo` over JDBC and prints the row count.

## M1b: local PySpark bronze -> silver -> gold + dbt parity

```powershell
.\spark\Run_M1.cmd
```

Or run the two jobs manually:

```powershell
$pkgs = "org.postgresql:postgresql:42.7.4,io.delta:delta-spark_2.12:3.0.0"
docker compose -f docker-compose.spark.yml run --rm spark `
  /opt/spark/bin/spark-submit --master local[2] --driver-memory 1g `
  --conf spark.jars.ivy=/tmp/.ivy2 --packages $pkgs `
  /opt/spark/smoke/jobs/build_gold.py

docker compose -f docker-compose.spark.yml run --rm spark `
  /opt/spark/bin/spark-submit --master local[2] --driver-memory 1g `
  --conf spark.jars.ivy=/tmp/.ivy2 --packages $pkgs `
  /opt/spark/smoke/jobs/parity_check.py
```

Current scope:

Silver, parsed from `bronze.matches` JSONB:

- `stg_matches`
- `stg_match_players`
- `stg_picks_bans`

Reference silver:

- `stg_heroes`
- `stg_hero_stats`
- `stg_teams`

Gold:

- `dim_hero`
- `dim_team`
- `fact_matches`
- `fact_match_players` (core columns)
- `fact_picks_bans`

Output is local Delta at `spark/delta/silver/` and `spark/delta/gold/`
(gitignored). The parity check compares row counts, key sets, and aggregate
metrics against the dbt silver and gold layers in PostgreSQL.

Expected rows:

- `stg_matches`: 1,500
- `stg_match_players`: 14,992
- `stg_picks_bans`: 30,124
- `dim_hero`: 128
- `dim_team`: 21,893
- `fact_matches`: 1,500
- `fact_match_players`: 14,992
- `fact_picks_bans`: 30,124

## Next M1 steps

1. Add the remaining core gold tables and enriched `fact_match_players` columns.
2. Add row-level hash parity, not just counts and aggregates.
3. Add a Spark CI workflow.
4. Move the jobs to Databricks using Auto Loader, Delta, and Unity Catalog.

## Memory

Keep the Spark driver at 1 GB on the 16 GB laptop. Do not run Spark and a full
dbt rebuild at the same time.

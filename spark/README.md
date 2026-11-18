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

## M1a: local PySpark gold + dbt parity

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

Current M1a scope:

- `dim_hero`
- `dim_team`
- `fact_matches`
- `fact_match_players` (core columns)
- `fact_picks_bans`

Output is local Delta at `spark/delta/gold/` (gitignored). The parity check
compares row counts, key sets, and aggregate metrics against the dbt gold layer
in PostgreSQL.

M1a passes with:

- `dim_hero`: 128 rows
- `dim_team`: 21,893 rows
- `fact_matches`: 1,500 rows
- `fact_match_players`: 14,992 rows
- `fact_picks_bans`: 30,124 rows

## Next M1 steps

1. Replace the silver JDBC reads with bronze JSONB parsing in Spark.
2. Add the remaining core gold tables and enriched `fact_match_players` columns.
3. Move the jobs to Databricks using Auto Loader, Delta, and Unity Catalog.

## Memory

Keep the Spark driver at 1 GB on the 16 GB laptop. Do not run Spark and a full
dbt rebuild at the same time.

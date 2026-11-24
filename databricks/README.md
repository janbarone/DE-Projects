# Databricks / Azure entry points

M2 uses the same PySpark logic as local M1, with two cloud-specific pieces:

1. `bronze_autoloader.py` - reads raw match JSON from ADLS with Auto Loader and
   writes `dota_catalog.bronze.matches`.
2. `load_reference.py` - loads leagues, players, teams, hero stats, and
   constants into the five bronze reference tables.

## Environment

Set these on the Databricks cluster/job:

```text
DOTA_ENV=cloud
DOTA_CATALOG=dota_catalog
DOTA_RAW_PATH=abfss://dota@<storage>.dfs.core.windows.net/raw/proMatches
DOTA_CHECKPOINT_PATH=abfss://dota@<storage>.dfs.core.windows.net/checkpoints/bronze_matches
```

Local defaults are in `spark/jobs/config.py`.

## Run order

1. Upload `demo_data` to ADLS `raw/`.
2. Run `bronze_autoloader.py` once with `trigger(availableNow=True)`.
3. Run `load_reference.py --raw-base <ADLS raw path>`.
4. Run the local silver/gold jobs with `DOTA_ENV=cloud` and Unity Catalog.
5. Compare counts with local Spark/dbt.

## Cost guardrails

- Use a small single-node or 2-worker cluster.
- Auto-terminate after 10-15 minutes.
- Use the 1,500-match `demo_data`, not the 29k scrape, for the first run.
- Pause the SQL warehouse when idle.

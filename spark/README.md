# Spark / PySpark (M0-M1)

M0 local smoke test. This is the zero-cost Spark leg before Azure/Databricks.

## Run the M0 smoke test

```powershell
docker compose up -d postgres
docker compose -f docker-compose.spark.yml run --rm spark \
  /opt/spark/bin/spark-submit --master local[2] \
  --driver-memory 512m /opt/spark/smoke/smoke.py
```

It reads `bronze.matches` from `dota_demo` over JDBC and prints the row count.
The first run downloads the Postgres JDBC driver through Spark packages.

## Memory

Keep the Spark driver at 512 MB on the 16 GB laptop. Do not run Spark and a
full dbt rebuild at the same time.

## M1 direction

Mirror `transform/models/` under `spark/jobs/`, write Delta tables locally, and
add a parity check against the dbt gold tables. See
`docs/cloud_azure_plan.md` for the milestone checklist.

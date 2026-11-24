"""M2: Auto Loader raw match JSON into dota_catalog.bronze.matches.

Run this as a Databricks notebook/job with DOTA_ENV=cloud. The raw path and
checkpoint can be overridden with DOTA_RAW_PATH and DOTA_CHECKPOINT_PATH.
"""
import sys
from pathlib import Path

from pyspark.sql import functions as F

sys.path.append(str(Path(__file__).resolve().parents[1] / "spark" / "jobs"))
import config  # noqa: E402
from common import spark_session  # noqa: E402

spark = spark_session("dota-cloud-bronze-autoloader")

raw = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "text")
    .option("cloudFiles.schemaEvolutionMode", "none")
    .option("cloudFiles.includeExistingFiles", "true")
    .load(config.RAW_PATH)
    .withColumn("payload", F.col("value"))
    .withColumn("match_id", F.get_json_object("payload", "$.match_id").cast("long"))
    .withColumn("source_file", F.input_file_name())
    .withColumn("source_fetched_at", F.current_timestamp())
    .withColumn("loaded_at", F.current_timestamp())
    .filter(F.col("match_id").isNotNull())
    .select("match_id", "payload", "source_fetched_at", "loaded_at", "source_file")
)

query = (
    raw.writeStream.format("delta")
    .option("checkpointLocation", config.CHECKPOINT_PATH)
    .trigger(availableNow=True)
    .toTable(config.table("bronze", "matches"))
)
query.awaitTermination()
print(f"bronze.matches rows={spark.table(config.table('bronze', 'matches')).count()}")

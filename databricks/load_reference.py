"""M2: load reference JSON from ADLS (or a local path) into bronze tables.

This is the cloud counterpart of scripts/load_bronze.py for the five
reference tables. Match files use bronze_autoloader.py instead.

Run locally against demo_data:
    DOTA_ENV=local python databricks/load_reference.py --raw-base /opt/spark/demo_data

Run in Databricks with DOTA_ENV=cloud and DOTA_RAW_BASE set to the ADLS raw
container; it writes Unity Catalog bronze tables.
"""
import argparse
import sys
from pathlib import Path

from pyspark.sql import functions as F
from pyspark.sql import types as T

_root = Path(__file__).resolve().parents[1]
for _candidate in (_root / "spark" / "jobs", _root / "jobs"):
    if _candidate.exists():
        sys.path.append(str(_candidate))
import config  # noqa: E402
from common import spark_session, write_delta  # noqa: E402

LEAGUE_SCHEMA = T.ArrayType(T.StructType([
    T.StructField("leagueid", T.IntegerType()),
    T.StructField("name", T.StringType()),
    T.StructField("tier", T.StringType()),
    T.StructField("ticket", T.StringType()),
    T.StructField("banner", T.StringType()),
    T.StructField("timestamp_fetched", T.StringType()),
]))

PLAYER_SCHEMA = T.ArrayType(T.StructType([
    T.StructField("account_id", T.IntegerType()),
    T.StructField("name", T.StringType()),
    T.StructField("rank_tier", T.IntegerType()),
    T.StructField("team_id", T.IntegerType()),
    T.StructField("avatarmedium", T.StringType()),
    T.StructField("timestamp_fetched", T.StringType()),
]))

TEAM_SCHEMA = T.ArrayType(T.StructType([
    T.StructField("team_id", T.IntegerType()),
    T.StructField("name", T.StringType()),
    T.StructField("tag", T.StringType()),
    T.StructField("rating", T.DoubleType()),
    T.StructField("wins", T.IntegerType()),
    T.StructField("losses", T.IntegerType()),
    T.StructField("logo_url", T.StringType()),
    T.StructField("timestamp_fetched", T.StringType()),
]))

HERO_STATS_SCHEMA = T.ArrayType(T.StructType([
    T.StructField("id", T.IntegerType()),
    T.StructField("pro_pick", T.IntegerType()),
    T.StructField("pro_win", T.IntegerType()),
    T.StructField("pro_ban", T.IntegerType()),
    T.StructField("pub_pick", T.IntegerType()),
    T.StructField("pub_win", T.IntegerType()),
    T.StructField("timestamp_fetched", T.StringType()),
]))

spark = spark_session("dota-cloud-reference-loader")


def read_texts(path: str):
    return spark.createDataFrame(spark.sparkContext.wholeTextFiles(path), ["path", "value"])


def read_array(path: str, schema):
    return (
        read_texts(path)
        .select(F.from_json("value", schema).alias("records"))
        .select(F.explode("records").alias("r"))
    )


def source_ts(record):
    return F.coalesce(
        F.to_timestamp(F.get_json_object(F.to_json(record), "$.timestamp_fetched")),
        F.current_timestamp(),
    )


def write_reference(df, table: str):
    write_delta(df, table, layer="bronze")
    print(f"bronze.{table} rows={df.count()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-base", default=config.RAW_BASE)
    args = parser.parse_args()
    raw = args.raw_base.rstrip("/")

    leagues = read_array(f"{raw}/leagues/leagues.json", LEAGUE_SCHEMA).select(
        F.col("r.leagueid").alias("leagueid"),
        F.to_json("r").alias("payload"),
        source_ts("r").alias("source_fetched_at"),
        F.current_timestamp().alias("loaded_at"),
    ).filter(F.col("leagueid").isNotNull())
    write_reference(leagues, "leagues")

    players = read_array(f"{raw}/proPlayers/proPlayers.json", PLAYER_SCHEMA).select(
        F.col("r.account_id").alias("account_id"),
        F.to_json("r").alias("payload"),
        source_ts("r").alias("source_fetched_at"),
        F.current_timestamp().alias("loaded_at"),
    ).filter(F.col("account_id").isNotNull())
    write_reference(players, "players")

    teams = read_array(f"{raw}/teams/teams.json", TEAM_SCHEMA).select(
        F.col("r.team_id").alias("team_id"),
        F.to_json("r").alias("payload"),
        source_ts("r").alias("source_fetched_at"),
        F.current_timestamp().alias("loaded_at"),
    ).filter(F.col("team_id").isNotNull())
    write_reference(teams, "teams")

    hero_stats = read_array(f"{raw}/heroStats/heroStats.json", HERO_STATS_SCHEMA).select(
        F.col("r.id").alias("id"),
        F.to_json("r").alias("payload"),
        source_ts("r").alias("source_fetched_at"),
        F.current_timestamp().alias("loaded_at"),
    ).filter(F.col("id").isNotNull())
    write_reference(hero_stats, "hero_stats")

    constants = (
        read_texts(f"{raw}/constants/*.json")
        .withColumn("resource", F.regexp_extract(F.col("path"), r"/([^/]+)\.json$", 1))
        .withColumn("payload", F.col("value"))
        .withColumn("source_fetched_at", F.current_timestamp())
        .withColumn("loaded_at", F.current_timestamp())
        .select("resource", "payload", "source_fetched_at", "loaded_at")
        .filter(F.col("resource") != "")
    )
    write_reference(constants, "constants")

    spark.stop()


if __name__ == "__main__":
    main()

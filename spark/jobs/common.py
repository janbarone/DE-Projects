"""Shared Spark/JDBC/Delta helpers for the local M1 jobs."""
import os

from pyspark.sql import DataFrame, SparkSession

JDBC_URL = os.environ.get(
    "DOTA_JDBC_URL", "jdbc:postgresql://host.docker.internal:5432/dota_demo"
)
JDBC_USER = os.environ.get("DOTA_JDBC_USER", "postgres")
JDBC_PASSWORD = os.environ.get("DOTA_JDBC_PASSWORD", "postgres")
DELTA_DIR = os.environ.get("DOTA_DELTA_DIR", "/opt/spark/delta")

JDBC_PROPS = {
    "user": JDBC_USER,
    "password": JDBC_PASSWORD,
    "driver": "org.postgresql.Driver",
}


def spark_session(app_name: str) -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def read_table(spark: SparkSession, table: str) -> DataFrame:
    return spark.read.jdbc(url=JDBC_URL, table=table, properties=JDBC_PROPS)


def read_silver(spark: SparkSession, name: str) -> DataFrame:
    return spark.read.format("delta").load(f"{DELTA_DIR}/silver/{name}")


def write_delta(df: DataFrame, name: str, layer: str = "gold") -> str:
    path = f"{DELTA_DIR}/{layer}/{name}"
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)
    return path

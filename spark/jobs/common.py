"""Shared Spark/JDBC/Delta helpers for the local and cloud jobs."""
import config
from pyspark.sql import DataFrame, SparkSession

DELTA_DIR = config.DELTA_DIR


def spark_session(app_name: str) -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
    )
    return builder.getOrCreate()


def read_table(spark: SparkSession, table: str) -> DataFrame:
    """Read a local PostgreSQL table through JDBC."""
    return spark.read.jdbc(
        url=config.JDBC_URL,
        table=table,
        properties={
            "user": config.JDBC_USER,
            "password": config.JDBC_PASSWORD,
            "driver": "org.postgresql.Driver",
        },
    )


def read_bronze(spark: SparkSession, name: str) -> DataFrame:
    """Read a bronze table from local Postgres or cloud Unity Catalog."""
    if config.IS_CLOUD:
        return spark.read.table(config.table("bronze", name))
    return read_table(spark, f"bronze.{name}")


def read_silver(spark: SparkSession, name: str) -> DataFrame:
    if config.IS_CLOUD:
        return spark.read.table(config.table("silver", name))
    return spark.read.format("delta").load(config.delta_path("silver", name))


def read_gold(spark: SparkSession, name: str) -> DataFrame:
    if config.IS_CLOUD:
        return spark.read.table(config.table("gold", name))
    return spark.read.format("delta").load(config.delta_path("gold", name))


def write_delta(df: DataFrame, name: str, layer: str = "gold") -> str:
    if config.IS_CLOUD:
        target = config.table(layer, name)
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(target)
        return target
    path = config.delta_path(layer, name)
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)
    return path

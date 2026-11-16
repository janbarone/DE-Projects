"""M0 smoke test: read bronze.matches from Postgres through Spark JDBC."""
import os

from pyspark.sql import SparkSession

url = os.environ.get("DOTA_JDBC_URL", "jdbc:postgresql://host.docker.internal:5432/dota_demo")
user = os.environ.get("DOTA_JDBC_USER", "postgres")
password = os.environ.get("DOTA_JDBC_PASSWORD", "postgres")

spark = (
    SparkSession.builder.appName("dota-m0-smoke")
    .config("spark.jars.packages", "org.postgresql:postgresql:42.7.4")
    .config("spark.driver.memory", "512m")
    .getOrCreate()
)
try:
    df = spark.read.jdbc(url=url, table="bronze.matches", properties={
        "user": user, "password": password, "driver": "org.postgresql.Driver",
    })
    print(f"bronze.matches rows: {df.count()}")
    print(f"columns: {', '.join(df.columns)}")
finally:
    spark.stop()

"""Local/cloud configuration for Spark jobs.

Local mode uses the Docker Postgres Bronze and local Delta paths.
Cloud mode uses Unity Catalog tables and Databricks/ADLS paths.
"""
import os

ENV = os.environ.get("DOTA_ENV", "local").strip().lower()
IS_CLOUD = ENV == "cloud"

CATALOG = os.environ.get("DOTA_CATALOG", "dota_catalog")

DELTA_DIR = os.environ.get("DOTA_DELTA_DIR", "/opt/spark/delta")
RAW_PATH = os.environ.get(
    "DOTA_RAW_PATH",
    "abfss://dota@stadotapipeline.dfs.core.windows.net/raw/proMatches",
)
BRONZE_MATCHES_PATH = os.environ.get(
    "DOTA_BRONZE_MATCHES_PATH",
    "abfss://dota@stadotapipeline.dfs.core.windows.net/bronze/matches",
)
CHECKPOINT_PATH = os.environ.get(
    "DOTA_CHECKPOINT_PATH",
    "abfss://dota@stadotapipeline.dfs.core.windows.net/checkpoints/bronze_matches",
)
JDBC_URL = os.environ.get(
    "DOTA_JDBC_URL", "jdbc:postgresql://host.docker.internal:5432/dota_demo"
)
JDBC_USER = os.environ.get("DOTA_JDBC_USER", "postgres")
JDBC_PASSWORD = os.environ.get("DOTA_JDBC_PASSWORD", "postgres")


def table(layer: str, name: str) -> str:
    """Fully qualified Unity Catalog table name."""
    return f"{CATALOG}.{layer}.{name}"


def delta_path(layer: str, name: str) -> str:
    """Local Delta path for the given layer/table."""
    return f"{DELTA_DIR}/{layer}/{name}"

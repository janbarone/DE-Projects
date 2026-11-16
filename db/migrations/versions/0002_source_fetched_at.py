"""Add source_fetched_at to bronze tables.

Revision ID: 0002_source_fetched_at
Revises: 0001_bronze_schema
Create Date: 2026-11-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_source_fetched_at"
down_revision = "0001_bronze_schema"
branch_labels = None
depends_on = None

TABLES = ("matches", "leagues", "players", "teams", "hero_stats", "constants")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=True),
            schema="bronze",
        )
        # Existing rows predate the column; loaded_at is the best available
        # approximation until the next scrape/load refreshes them.
        op.execute(
            f"update bronze.{table} set source_fetched_at = loaded_at "
            "where source_fetched_at is null"
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "source_fetched_at", schema="bronze")

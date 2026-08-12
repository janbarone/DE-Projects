"""Create bronze schema and raw tables.

Mirrors db/init/01_schemas.sql + db/init/02_bronze_tables.sql as a versioned
migration so schema changes are reproducible over time.

Revision ID: 0001_bronze_schema
Revises:
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_bronze_schema"
down_revision = None
branch_labels = None
depends_on = None


def _bronze_tables():
    tables = {
        "matches": ("match_id", sa.BigInteger),
        "leagues": ("leagueid", sa.Integer),
        "players": ("account_id", sa.Integer),
        "teams": ("team_id", sa.Integer),
        "hero_stats": ("id", sa.Integer),
    }
    for name, (pk, pk_type) in tables.items():
        op.create_table(
            name,
            sa.Column(pk, pk_type, primary_key=True),
            sa.Column("payload", JSONB, nullable=False),
            sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema="bronze",
        )
        op.create_index(f"idx_bronze_{name}_loaded_at", name, ["loaded_at"], schema="bronze")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    # constants has a text key instead of an integer.
    op.create_table(
        "constants",
        sa.Column("resource", sa.Text, primary_key=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="bronze",
    )

    _bronze_tables()


def downgrade() -> None:
    for name in ("matches", "leagues", "players", "teams", "hero_stats", "constants"):
        op.drop_table(name, schema="bronze")
    op.execute("DROP SCHEMA IF EXISTS bronze")

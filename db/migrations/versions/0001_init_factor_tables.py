"""init factor tables

Revision ID: 0001_init_factor_tables
Revises: 
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_init_factor_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factor_metadata",
        sa.Column("factor_key", sa.String(length=128), nullable=False),
        sa.Column("factor_name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=False),
        sa.Column("python_entry", sa.String(length=512), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("parameter_schema", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("factor_key"),
    )
    op.create_index(op.f("ix_factor_metadata_category"), "factor_metadata", ["category"], unique=False)
    op.create_index(op.f("ix_factor_metadata_factor_name"), "factor_metadata", ["factor_name"], unique=False)
    op.create_index(op.f("ix_factor_metadata_status"), "factor_metadata", ["status"], unique=False)
    op.create_index(op.f("ix_factor_metadata_version"), "factor_metadata", ["version"], unique=False)

    op.create_table(
        "factor_runs",
        sa.Column("calc_batch_id", sa.String(length=128), nullable=False),
        sa.Column("factor_name", sa.String(length=128), nullable=False),
        sa.Column("factor_version", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("universe_name", sa.String(length=128), nullable=False),
        sa.Column("provider_uri", sa.String(length=512), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("instrument_limit", sa.Integer(), nullable=True),
        sa.Column("artifact_path", sa.String(length=1024), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.String(length=4096), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("calc_batch_id"),
    )
    op.create_index(op.f("ix_factor_runs_computed_at"), "factor_runs", ["computed_at"], unique=False)
    op.create_index(op.f("ix_factor_runs_end_date"), "factor_runs", ["end_date"], unique=False)
    op.create_index(op.f("ix_factor_runs_factor_name"), "factor_runs", ["factor_name"], unique=False)
    op.create_index(op.f("ix_factor_runs_factor_version"), "factor_runs", ["factor_version"], unique=False)
    op.create_index(op.f("ix_factor_runs_mode"), "factor_runs", ["mode"], unique=False)
    op.create_index(op.f("ix_factor_runs_start_date"), "factor_runs", ["start_date"], unique=False)
    op.create_index(op.f("ix_factor_runs_status"), "factor_runs", ["status"], unique=False)
    op.create_index(op.f("ix_factor_runs_universe_name"), "factor_runs", ["universe_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_factor_runs_universe_name"), table_name="factor_runs")
    op.drop_index(op.f("ix_factor_runs_status"), table_name="factor_runs")
    op.drop_index(op.f("ix_factor_runs_start_date"), table_name="factor_runs")
    op.drop_index(op.f("ix_factor_runs_mode"), table_name="factor_runs")
    op.drop_index(op.f("ix_factor_runs_factor_version"), table_name="factor_runs")
    op.drop_index(op.f("ix_factor_runs_factor_name"), table_name="factor_runs")
    op.drop_index(op.f("ix_factor_runs_end_date"), table_name="factor_runs")
    op.drop_index(op.f("ix_factor_runs_computed_at"), table_name="factor_runs")
    op.drop_table("factor_runs")

    op.drop_index(op.f("ix_factor_metadata_version"), table_name="factor_metadata")
    op.drop_index(op.f("ix_factor_metadata_status"), table_name="factor_metadata")
    op.drop_index(op.f("ix_factor_metadata_factor_name"), table_name="factor_metadata")
    op.drop_index(op.f("ix_factor_metadata_category"), table_name="factor_metadata")
    op.drop_table("factor_metadata")


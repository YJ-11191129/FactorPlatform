"""roadshow data artifacts

Revision ID: 0003_roadshow_data_artifacts
Revises: 0002_audit_tasks_analysis
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_roadshow_data_artifacts"
down_revision = "0002_audit_tasks_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_data_sources",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("storage_origin", sa.String(length=1024), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("row_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("freshness_status", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_market_data_sources_market", "market_data_sources", ["market"], unique=False)
    op.create_index("ix_market_data_sources_freshness_status", "market_data_sources", ["freshness_status"], unique=False)

    op.create_table(
        "market_universe_members",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("universe", sa.String(length=64), nullable=False),
        sa.Column("asset_code", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.PrimaryKeyConstraint("source_id", "universe", "asset_code"),
    )
    op.create_index("ix_market_universe_members_asset", "market_universe_members", ["asset_code"], unique=False)
    op.create_index("ix_market_universe_members_source_universe", "market_universe_members", ["source_id", "universe"], unique=False)

    op.create_table(
        "daily_ohlcv",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("asset_code", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=True),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("adj_factor", sa.Float(), nullable=True),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.PrimaryKeyConstraint("source_id", "trade_date", "asset_code"),
    )
    op.create_index("ix_daily_ohlcv_source_date", "daily_ohlcv", ["source_id", "trade_date"], unique=False)
    op.create_index("ix_daily_ohlcv_source_asset_date", "daily_ohlcv", ["source_id", "asset_code", "trade_date"], unique=False)
    op.create_index("ix_daily_ohlcv_market_date", "daily_ohlcv", ["market", "trade_date"], unique=False)

    op.create_table(
        "structured_market_datasets",
        sa.Column("record_id", sa.String(length=96), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("dataset_type", sa.String(length=96), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("asset_code", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index("ix_structured_market_source_dataset_date", "structured_market_datasets", ["source_id", "dataset_type", "trade_date"], unique=False)
    op.create_index("ix_structured_market_asset", "structured_market_datasets", ["asset_code"], unique=False)

    op.create_table(
        "artifact_registry",
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("download_path", sa.String(length=1024), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("artifact_id"),
    )
    op.create_index("ix_artifact_registry_run_id", "artifact_registry", ["run_id"], unique=False)
    op.create_index("ix_artifact_registry_artifact_type", "artifact_registry", ["artifact_type"], unique=False)
    op.create_index("ix_artifact_registry_checksum", "artifact_registry", ["checksum_sha256"], unique=False)

    op.create_table(
        "roadshow_seed_state",
        sa.Column("seed_id", sa.String(length=64), nullable=False),
        sa.Column("dump_checksum", sa.String(length=64), nullable=False),
        sa.Column("dump_path", sa.String(length=1024), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.PrimaryKeyConstraint("seed_id"),
    )


def downgrade() -> None:
    op.drop_table("roadshow_seed_state")

    op.drop_index("ix_artifact_registry_checksum", table_name="artifact_registry")
    op.drop_index("ix_artifact_registry_artifact_type", table_name="artifact_registry")
    op.drop_index("ix_artifact_registry_run_id", table_name="artifact_registry")
    op.drop_table("artifact_registry")

    op.drop_index("ix_structured_market_asset", table_name="structured_market_datasets")
    op.drop_index("ix_structured_market_source_dataset_date", table_name="structured_market_datasets")
    op.drop_table("structured_market_datasets")

    op.drop_index("ix_daily_ohlcv_market_date", table_name="daily_ohlcv")
    op.drop_index("ix_daily_ohlcv_source_asset_date", table_name="daily_ohlcv")
    op.drop_index("ix_daily_ohlcv_source_date", table_name="daily_ohlcv")
    op.drop_table("daily_ohlcv")

    op.drop_index("ix_market_universe_members_source_universe", table_name="market_universe_members")
    op.drop_index("ix_market_universe_members_asset", table_name="market_universe_members")
    op.drop_table("market_universe_members")

    op.drop_index("ix_market_data_sources_freshness_status", table_name="market_data_sources")
    op.drop_index("ix_market_data_sources_market", table_name="market_data_sources")
    op.drop_table("market_data_sources")

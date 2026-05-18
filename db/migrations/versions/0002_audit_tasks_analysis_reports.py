"""audit tasks analysis reports

Revision ID: 0002_audit_tasks_analysis
Revises: 0001_init_factor_tables
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_audit_tasks_analysis"
down_revision = "0001_init_factor_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource", sa.String(length=256), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_actor"), "audit_logs", ["actor"], unique=False)
    op.create_index(op.f("ix_audit_logs_request_id"), "audit_logs", ["request_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_resource"), "audit_logs", ["resource"], unique=False)
    op.create_index(op.f("ix_audit_logs_role"), "audit_logs", ["role"], unique=False)
    op.create_index(op.f("ix_audit_logs_status_code"), "audit_logs", ["status_code"], unique=False)

    op.create_table(
        "task_jobs",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(length=4096), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(op.f("ix_task_jobs_actor"), "task_jobs", ["actor"], unique=False)
    op.create_index(op.f("ix_task_jobs_celery_task_id"), "task_jobs", ["celery_task_id"], unique=False)
    op.create_index(op.f("ix_task_jobs_job_type"), "task_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_task_jobs_role"), "task_jobs", ["role"], unique=False)
    op.create_index(op.f("ix_task_jobs_status"), "task_jobs", ["status"], unique=False)

    op.create_table(
        "analysis_results",
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("analysis_type", sa.String(length=128), nullable=False),
        sa.Column("calc_batch_id", sa.String(length=128), nullable=False),
        sa.Column("factor_name", sa.String(length=128), nullable=False),
        sa.Column("factor_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String(length=1024), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("analysis_id"),
    )
    op.create_index(op.f("ix_analysis_results_analysis_type"), "analysis_results", ["analysis_type"], unique=False)
    op.create_index(op.f("ix_analysis_results_calc_batch_id"), "analysis_results", ["calc_batch_id"], unique=False)
    op.create_index(op.f("ix_analysis_results_factor_name"), "analysis_results", ["factor_name"], unique=False)
    op.create_index(op.f("ix_analysis_results_factor_version"), "analysis_results", ["factor_version"], unique=False)
    op.create_index(op.f("ix_analysis_results_status"), "analysis_results", ["status"], unique=False)

    op.create_table(
        "report_artifacts",
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("report_type", sa.String(length=128), nullable=False),
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("html_path", sa.String(length=1024), nullable=False),
        sa.Column("pdf_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_index(op.f("ix_report_artifacts_analysis_id"), "report_artifacts", ["analysis_id"], unique=False)
    op.create_index(op.f("ix_report_artifacts_report_type"), "report_artifacts", ["report_type"], unique=False)
    op.create_index(op.f("ix_report_artifacts_status"), "report_artifacts", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_report_artifacts_status"), table_name="report_artifacts")
    op.drop_index(op.f("ix_report_artifacts_report_type"), table_name="report_artifacts")
    op.drop_index(op.f("ix_report_artifacts_analysis_id"), table_name="report_artifacts")
    op.drop_table("report_artifacts")

    op.drop_index(op.f("ix_analysis_results_status"), table_name="analysis_results")
    op.drop_index(op.f("ix_analysis_results_factor_version"), table_name="analysis_results")
    op.drop_index(op.f("ix_analysis_results_factor_name"), table_name="analysis_results")
    op.drop_index(op.f("ix_analysis_results_calc_batch_id"), table_name="analysis_results")
    op.drop_index(op.f("ix_analysis_results_analysis_type"), table_name="analysis_results")
    op.drop_table("analysis_results")

    op.drop_index(op.f("ix_task_jobs_status"), table_name="task_jobs")
    op.drop_index(op.f("ix_task_jobs_role"), table_name="task_jobs")
    op.drop_index(op.f("ix_task_jobs_job_type"), table_name="task_jobs")
    op.drop_index(op.f("ix_task_jobs_celery_task_id"), table_name="task_jobs")
    op.drop_index(op.f("ix_task_jobs_actor"), table_name="task_jobs")
    op.drop_table("task_jobs")

    op.drop_index(op.f("ix_audit_logs_status_code"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_role"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_resource"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_request_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")

"""initial tables

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("delivery_id", sa.String(64), nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_webhook_deliveries_delivery_id", "webhook_deliveries", ["delivery_id"], unique=True
    )

    op.create_table(
        "review_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=True),
        sa.Column("delivery_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result", sa.String(64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_review_jobs_idempotency_key", "review_jobs", ["idempotency_key"], unique=True
    )
    op.create_index("ix_review_jobs_repo_full_name", "review_jobs", ["repo_full_name"])
    op.create_index("ix_review_jobs_status", "review_jobs", ["status"])

    op.create_table(
        "bot_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("github_comment_id", sa.BigInteger(), nullable=False),
        sa.Column("last_head_sha", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("repo_full_name", "pr_number", name="uq_bot_comment_pr"),
    )


def downgrade() -> None:
    op.drop_table("bot_comments")
    op.drop_table("review_jobs")
    op.drop_table("webhook_deliveries")

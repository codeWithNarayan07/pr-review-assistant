"""add review risk details

Revision ID: 38b07dfcb57a
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "38b07dfcb57a"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_jobs",
        sa.Column("risk_details", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_jobs", "risk_details")

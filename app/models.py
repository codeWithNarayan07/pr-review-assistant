import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class JobStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    done = "done"
    skipped = "skipped"
    failed = "failed"


class WebhookDelivery(Base):
    """One row per GitHub delivery id, so a redelivered event is never processed twice."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event: Mapped[str] = mapped_column(String(64))
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewJob(Base):
    __tablename__ = "review_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # "owner/repo#number@sha" - one job per PR commit, enforced by the unique constraint
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String(64))
    installation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delivery_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.pending.value, index=True)
    result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BotComment(Base):
    """The single comment the bot keeps updated on each pull request."""

    __tablename__ = "bot_comments"
    __table_args__ = (UniqueConstraint("repo_full_name", "pr_number", name="uq_bot_comment_pr"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_full_name: Mapped[str] = mapped_column(String(255))
    pr_number: Mapped[int] = mapped_column(Integer)
    github_comment_id: Mapped[int] = mapped_column(BigInteger)
    last_head_sha: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

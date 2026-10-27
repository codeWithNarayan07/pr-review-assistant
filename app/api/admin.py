"""Read-only job statistics. Disabled (404) unless ADMIN_TOKEN is set."""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_settings_dep
from app.models import JobStatus, ReviewJob

router = APIRouter(prefix="/admin")


def require_admin(
    settings=Depends(get_settings_dep),
    authorization: str | None = Header(None),
):
    if not settings.admin_token:
        raise HTTPException(404)
    expected = f"Bearer {settings.admin_token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(401, "Invalid admin token")


@router.get("/stats", dependencies=[Depends(require_admin)])
async def stats(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(select(ReviewJob.status, func.count()).group_by(ReviewJob.status))
    ).all()

    counts = {status: 0 for status in (s.value for s in JobStatus)}
    counts.update({status: n for status, n in rows})

    done = (
        await session.execute(
            select(ReviewJob.started_at, ReviewJob.finished_at).where(
                ReviewJob.status == JobStatus.done.value,
                ReviewJob.finished_at.is_not(None),
            )
        )
    ).all()

    durations = [(f - s).total_seconds() for s, f in done if s and f]

    return {
        "jobs_by_status": counts,
        "avg_processing_seconds": (
            round(sum(durations) / len(durations), 2) if durations else None
        ),
    }


@router.get("/jobs", dependencies=[Depends(require_admin)])
async def jobs(limit: int = 50, session: AsyncSession = Depends(get_session)):
    result = await session.scalars(
        select(ReviewJob).order_by(ReviewJob.id.desc()).limit(min(max(limit, 1), 200))
    )

    return [
        {
            "id": j.id,
            "repo": j.repo_full_name,
            "pr": j.pr_number,
            "sha": j.head_sha[:7],
            "status": j.status,
            "result": j.result,
            "attempts": j.attempts,
            "error": j.error,
            "created_at": j.created_at,
            "risk_details": j.risk_details,
            "risk_level": (j.risk_details or {}).get("level"),
            "risk_count": (j.risk_details or {}).get("finding_count", 0),
        }
        for j in result
    ]

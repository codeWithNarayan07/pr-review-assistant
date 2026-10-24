"""The review itself: fetch the PR, analyse it, ask the LLM, post/update one comment."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import LLMError
from app.models import BotComment, ReviewJob
from app.schemas import ReviewContext
from app.services import diff_utils, formatter, risk_rules
from app.services.github_client import GitHubClient
from app.services.llm_client import LLMClient
from app.services.repo_config import load_repo_config
from app.services.secret_redaction import redact

log = logging.getLogger(__name__)


def _fallback_summary(report: risk_rules.RiskReport) -> str:
    where = f" in {', '.join(report.areas)}" if report.areas else ""
    return (
        f"This PR changes {report.file_count} file(s){where} "
        f"({report.changed_lines} changed lines)."
    )


async def run_review(
    job: ReviewJob,
    session: AsyncSession,
    gh: GitHubClient,
    llm: LLMClient,
    settings: Settings,
    *,
    final_attempt: bool = False,
) -> str:
    """Returns an outcome string: commented | updated | skipped:<reason>."""
    repo, number, sha = job.repo_full_name, job.pr_number, job.head_sha

    pr = await gh.get_pull(repo, number)
    if pr.get("state") != "open":
        return "skipped:closed"
    if pr["head"]["sha"] != sha:
        return "skipped:superseded"  # a newer commit has its own job

    config = await load_repo_config(gh, repo, sha)
    if not config.enabled:
        return "skipped:disabled"

    existing = await session.scalar(
        select(BotComment).where(BotComment.repo_full_name == repo, BotComment.pr_number == number)
    )
    if existing and existing.last_head_sha == sha:
        return "skipped:already_reviewed"

    files, truncated = await gh.list_pull_files(repo, number, settings.max_files_fetched)

    # Never send credentials to the LLM: redact every patch first.
    secrets_found = 0
    for f in files:
        if f.patch:
            f.patch, n = redact(f.patch)
            secrets_found += n

    prepared = diff_utils.prepare_diff(
        files,
        max_chars=settings.max_diff_chars,
        max_chars_per_file=settings.max_chars_per_file,
        extra_ignore=config.ignore_paths,
    )
    relevant = [f for f in files if not diff_utils.is_ignored(f.path, config.ignore_paths)]
    report = risk_rules.analyze(
        relevant,
        large_pr_lines=settings.large_pr_lines,
        large_pr_files=settings.large_pr_files,
        secrets_found=secrets_found,
        custom_rules=[r.model_dump() for r in config.custom_risks],
    )

    notes: list[str] = []
    ctx = ReviewContext(
        title=pr.get("title") or "",
        description=redact(pr.get("body") or "")[0],
        files_summary="\n".join(
            f"{f.path} ({f.status}, +{f.additions}/-{f.deletions})" for f in relevant[:100]
        ),
        diff_text=prepared.text,
    )
    review = None
    if prepared.text:
        try:
            review = await llm.review(ctx)
        except LLMError:
            if not final_attempt:
                raise  # let the worker retry
            notes.append("The AI summary was unavailable; showing automated checks only.")

    if truncated:
        notes.append(f"Only the first {settings.max_files_fetched} changed files were analysed.")
    if prepared.omitted:
        notes.append(f"{len(prepared.omitted)} file(s) were too large or had no diff to analyse.")

    rule_risks = [r.message for r in report.risks]
    llm_risks = [r for r in (review.risks if review else []) if r not in rule_risks]
    checklist = [r.checklist for r in report.risks if r.checklist]
    checklist += review.checklist if review else []
    checklist += config.extra_checklist

    body = formatter.render_comment(
        summary=review.summary if review else _fallback_summary(report),
        key_changes=review.key_changes if review else [],
        risks=rule_risks + llm_risks,
        checklist=list(dict.fromkeys(checklist)),
        head_sha=sha,
        notes=notes,
    )
    return await _upsert_comment(session, gh, existing, repo, number, sha, body)


async def _upsert_comment(session, gh, existing, repo, number, sha, body) -> str:
    outcome = "updated"
    comment_id = existing.github_comment_id if existing else None
    if comment_id is None:  # database has no record: maybe we commented before a crash
        comment_id = await gh.find_comment_with_marker(repo, number, formatter.MARKER)
    if comment_id is not None and not await gh.update_comment(repo, comment_id, body):
        comment_id = None  # a human deleted it; post a fresh one
    if comment_id is None:
        comment_id = await gh.create_comment(repo, number, body)
        outcome = "commented"

    if existing:
        existing.github_comment_id = comment_id
        existing.last_head_sha = sha
    else:
        session.add(
            BotComment(
                repo_full_name=repo,
                pr_number=number,
                github_comment_id=comment_id,
                last_head_sha=sha,
            )
        )
    await session.commit()
    return outcome

"""Format review findings into a clean GitHub pull-request comment."""

import re

MARKER = "<!-- pr-review-assistant:v1 -->"


def _clean(text: str, limit: int = 300) -> str:
    """Normalize text and prevent HTML injection and accidental @mentions."""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("@", "@\u200b")
    return text[:limit]


def _section(
    title: str,
    items: list[str],
    *,
    checkbox: bool = False,
) -> list[str]:
    if not items:
        return []

    prefix = "- [ ] " if checkbox else "- "
    cleaned_items = [f"{prefix}{_clean(item)}" for item in items]

    return ["", f"### {title}", "", *cleaned_items]


def render_comment(
    *,
    summary: str,
    key_changes: list[str],
    risks: list[str],
    checklist: list[str],
    head_sha: str,
    notes: list[str],
) -> str:
    """Render a structured, readable Markdown review comment."""
    lines = [
        MARKER,
        "# 🔍 PR Review Assistant",
        "",
        "> Automated first-pass code review",
        "",
        "## 📝 Summary",
        "",
        _clean(summary, 900),
    ]

    lines += _section("✨ Key Changes", key_changes)
    lines += _section("⚠️ Risks to Review", risks)
    lines += _section("✅ Review Checklist", checklist, checkbox=True)

    if notes:
        lines += ["", "### ℹ️ Additional Notes", ""]
        lines += [f"> {_clean(note)}" for note in notes]

    lines += [
        "",
        "---",
        "",
        f"**Commit reviewed:** `{head_sha[:7]}`",
        "",
        "*This review is automated. Please verify findings and use human judgment before merging.*",
    ]

    return "\n".join(lines)

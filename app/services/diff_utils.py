"""Decide which changed files are worth sending to the LLM, and fit them in a size budget."""

import fnmatch
from dataclasses import dataclass, field

from app.schemas import FileChange

DEFAULT_IGNORE = [
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.snap",
    "*_pb2.py",
    "*.generated.*",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.ico",
    "*.pdf",
    "*.woff",
    "*.woff2",
    "*.zip",
    "dist/*",
    "build/*",
    "node_modules/*",
    "vendor/*",
    "*/dist/*",
    "*/build/*",
    "*/node_modules/*",
    "*/vendor/*",
]


def is_ignored(path: str, extra: list[str] | None = None) -> bool:
    name = path.rsplit("/", 1)[-1]
    for pattern in [*DEFAULT_IGNORE, *(extra or [])]:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern):
            return True
    return False


@dataclass
class PreparedDiff:
    text: str
    included: list[str] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)  # relevant but did not fit / no patch
    ignored: list[str] = field(default_factory=list)  # noise (lock files, images, ...)


def prepare_diff(
    files: list[FileChange],
    *,
    max_chars: int,
    max_chars_per_file: int,
    extra_ignore: list[str] | None = None,
) -> PreparedDiff:
    result = PreparedDiff(text="")
    parts: list[str] = []
    used = 0
    for f in files:
        if is_ignored(f.path, extra_ignore):
            result.ignored.append(f.path)
            continue
        if not f.patch:  # binary, renamed without changes, or too large for GitHub to show
            result.omitted.append(f.path)
            continue
        patch = f.patch
        if len(patch) > max_chars_per_file:
            patch = patch[:max_chars_per_file] + "\n... [file diff truncated]"
        block = f"### {f.path} ({f.status}, +{f.additions}/-{f.deletions})\n{patch}\n"
        if used + len(block) > max_chars:
            result.omitted.append(f.path)
            continue
        parts.append(block)
        used += len(block)
        result.included.append(f.path)
    result.text = "\n".join(parts)
    return result

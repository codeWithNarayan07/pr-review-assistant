"""Cheap, deterministic checks that run with or without the LLM."""

import fnmatch
import re
from dataclasses import dataclass, field

from app.schemas import FileChange

_B = r"(?<![a-z])"  # "word" boundaries that treat _ and / as separators
_E = r"(?![a-z])"

# (key, path regex, risk message, checklist item)
_PATH_RULES: list[tuple[str, re.Pattern, str, str]] = [
    (
        "auth",
        re.compile(
            rf"{_B}(auth|authn|authz|authenticat\w*|authoriz\w*|login|oauth\w*|jwt|sessions?|passwords?|permissions?|rbac){_E}"
        ),
        "Touches authentication or authorization code",
        "Check that access control still behaves correctly (who can do what)",
    ),
    (
        "payments",
        re.compile(rf"{_B}(payments?|billing|stripe|invoices?|checkout|paypal|razorpay){_E}"),
        "Touches payment or billing code",
        "Verify amounts, currencies and failure handling for payments",
    ),
    (
        "migration",
        re.compile(r"(^|/)(migrations?|alembic)/|\.sql$"),
        "Contains a database migration or SQL change",
        "Confirm the migration is reversible and safe on a large production table",
    ),
    (
        "infra",
        re.compile(
            r"(^|/)(dockerfile|docker-compose[^/]*\.ya?ml|\.github/workflows/|terraform/|k8s/|helm/)"
            r"|\.tf$"
        ),
        "Changes build, CI or infrastructure configuration",
        "Check the pipeline and deployment config still work end to end",
    ),
    (
        "dependencies",
        re.compile(
            r"(^|/)(requirements[^/]*\.txt|pyproject\.toml|package\.json|go\.mod|cargo\.toml|"
            r"pom\.xml|build\.gradle|gemfile)$"
        ),
        "Adds or changes dependencies",
        "Review new or upgraded dependencies (licence, maintenance, known vulnerabilities)",
    ),
    (
        "secrets-config",
        re.compile(rf"(^|/)\.env|{_B}(secrets?|credentials?){_E}|\.pem$|\.key$"),
        "Touches configuration or files that may hold secrets",
        "Make sure no real credentials are committed",
    ),
]

_TEST_RE = re.compile(
    r"(^|/)(tests?|__tests__|specs?)/|(^|/)test_[^/]*$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$"
)
_SOURCE_EXT = {
    "py", "js", "jsx", "ts", "tsx", "java", "kt", "go", "rs", "rb", "php", "cs", "swift",
    "c", "cc", "cpp", "h", "hpp", "scala", "vue", "svelte",
}  # fmt: skip


@dataclass
class Risk:
    message: str
    checklist: str | None = None


@dataclass
class RiskReport:
    risks: list[Risk] = field(default_factory=list)
    file_count: int = 0
    changed_lines: int = 0
    tests_touched: bool = False
    source_touched: bool = False
    areas: list[str] = field(default_factory=list)


def is_test_file(path: str) -> bool:
    return bool(_TEST_RE.search(path.lower()))


def _is_source(path: str) -> bool:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    return ext in _SOURCE_EXT and not is_test_file(path)


def analyze(
    files: list[FileChange],
    *,
    large_pr_lines: int,
    large_pr_files: int,
    secrets_found: int = 0,
    custom_rules: list[dict] | None = None,
) -> RiskReport:
    report = RiskReport(file_count=len(files), changed_lines=sum(f.changes for f in files))
    seen: set[str] = set()

    def add(key: str, message: str, checklist: str | None = None) -> None:
        if key not in seen:
            seen.add(key)
            report.risks.append(Risk(message, checklist))

    if secrets_found:
        add(
            "secret",
            "Possible secret or credential found in the diff - verify and rotate it if real",
            "Remove any committed credentials and rotate them",
        )

    for f in files:
        lower = f.path.lower()
        if is_test_file(f.path):
            report.tests_touched = True
        elif _is_source(f.path):
            report.source_touched = True
        for key, pattern, message, checklist in _PATH_RULES:
            if pattern.search(lower):
                add(key, message, checklist)
        for rule in custom_rules or []:
            if fnmatch.fnmatch(f.path, rule["pattern"]):
                add(f"custom:{rule['pattern']}", rule["message"])

    if report.source_touched and not report.tests_touched:
        add(
            "no-tests",
            "Source files changed but no tests were added or updated",
            "Ask whether the new behaviour is covered by tests",
        )
    if report.changed_lines > large_pr_lines or report.file_count > large_pr_files:
        add(
            "large",
            f"Large change ({report.file_count} files, {report.changed_lines} lines) - "
            "hard to review in one pass",
            "Consider asking for the PR to be split into smaller pieces",
        )

    top_dirs = {f.path.split("/")[0] for f in files if "/" in f.path}
    report.areas = sorted(top_dirs)[:5]
    return report

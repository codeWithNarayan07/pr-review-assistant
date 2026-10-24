from app.schemas import FileChange
from app.services.diff_utils import is_ignored, prepare_diff
from app.services.risk_rules import analyze, is_test_file


def fc(path, add=5, dele=1, patch="@@ x @@\n+code", status="modified"):
    return FileChange(path, status, add, dele, patch)


def run(files, **kw):
    return analyze(files, large_pr_lines=600, large_pr_files=25, **kw)


def messages(report):
    return [r.message for r in report.risks]


def test_flags_auth_and_missing_tests():
    report = run([fc("app/auth/login.py")])
    msgs = messages(report)
    assert any("authentication" in m for m in msgs)
    assert any("no tests" in m for m in msgs)


def test_no_missing_tests_warning_when_tests_touched():
    report = run([fc("app/service.py"), fc("tests/test_service.py")])
    assert not any("no tests" in m for m in messages(report))
    assert report.tests_touched and report.source_touched


def test_docs_only_change_has_no_risks():
    assert run([fc("README.md")]).risks == []


def test_migration_infra_dependencies_payments():
    report = run(
        [
            fc("migrations/versions/0002_x.py"),
            fc(".github/workflows/ci.yml"),
            fc("requirements.txt"),
            fc("src/billing/invoice.py"),
        ]
    )
    msgs = " | ".join(messages(report))
    for word in ("migration", "infrastructure", "dependencies", "payment"):
        assert word in msgs


def test_large_pr_by_lines_and_by_files():
    assert any("Large" in m for m in messages(run([fc("a.md", add=700)])))
    many = [fc(f"docs/{i}.md") for i in range(30)]
    assert any("Large" in m for m in messages(run(many)))


def test_secret_flag_and_custom_rule():
    report = run(
        [fc("src/x.py")],
        secrets_found=1,
        custom_rules=[{"pattern": "src/*", "message": "Owned by the platform team"}],
    )
    msgs = " | ".join(messages(report))
    assert "secret" in msgs and "platform team" in msgs


def test_auth_pattern_does_not_match_inside_words():
    assert not any("authentication" in m for m in messages(run([fc("src/author_list.py")])))


def test_is_test_file():
    assert is_test_file("tests/test_a.py")
    assert is_test_file("src/app.test.ts")
    assert is_test_file("pkg/foo_test.go")
    assert not is_test_file("src/attest.py")


def test_ignore_rules():
    assert is_ignored("package-lock.json")
    assert is_ignored("web/dist/app.js")
    assert is_ignored("assets/logo.png")
    assert is_ignored("docs/gen.txt", ["docs/*"])
    assert not is_ignored("app/main.py")


def test_prepare_diff_respects_budgets_and_buckets_files():
    files = [
        fc("a.py", patch="x" * 100),
        fc("b.py", patch="y" * 100),
        fc("package-lock.json"),
        fc("img.bin", patch=None),
    ]
    out = prepare_diff(files, max_chars=150, max_chars_per_file=60)
    assert out.included == ["a.py"]
    assert "b.py" in out.omitted and "img.bin" in out.omitted
    assert out.ignored == ["package-lock.json"]
    assert "[file diff truncated]" in out.text

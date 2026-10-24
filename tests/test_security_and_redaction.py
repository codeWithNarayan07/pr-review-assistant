from app.services.rate_limit import SlidingWindowLimiter
from app.services.secret_redaction import REDACTED, redact
from app.services.security import sign, verify_signature


def test_valid_signature_passes():
    body = b'{"a": 1}'
    assert verify_signature("s3cret", body, sign("s3cret", body))


def test_wrong_secret_body_or_header_fails():
    body = b'{"a": 1}'
    good = sign("s3cret", body)
    assert not verify_signature("other", body, good)
    assert not verify_signature("s3cret", b"tampered", good)
    assert not verify_signature("s3cret", body, None)
    assert not verify_signature("s3cret", body, "sha1=abc")
    assert not verify_signature("", body, good)  # empty secret never validates


def test_redacts_common_credentials():
    text = (
        "key=AKIAIOSFODNN7EXAMPLE\n"
        "token ghp_" + "a" * 36 + "\n"
        'password = "hunter2hunter2"\n'
        "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----\n"
    )
    clean, count = redact(text)
    assert count == 4
    assert "AKIAIOSFODNN7EXAMPLE" not in clean
    assert "hunter2" not in clean
    assert "MIIabc" not in clean
    assert REDACTED in clean


def test_redaction_leaves_normal_code_alone():
    code = "def add(a, b):\n    return a + b  # password reset flow\n"
    assert redact(code) == (code, 0)


def test_rate_limiter_blocks_after_limit():
    limiter = SlidingWindowLimiter(limit=2)
    assert limiter.allow("ip") and limiter.allow("ip")
    assert not limiter.allow("ip")
    assert limiter.allow("other-ip")

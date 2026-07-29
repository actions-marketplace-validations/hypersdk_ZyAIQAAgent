from orchestrator.security.redaction import REDACTED, redact, redact_text


def test_recursive_secret_redaction():
    raw = {
        "auth": {
            "token": "abc",
            "headers": {"Authorization": "Bearer top-secret"},
        },
        "items": [{"client_secret": "x"}, {"safe": "ok"}],
    }
    clean = redact(raw)
    assert clean["auth"]["token"] == REDACTED
    assert clean["auth"]["headers"]["Authorization"] == REDACTED
    assert clean["items"][0]["client_secret"] == REDACTED
    assert clean["items"][1]["safe"] == "ok"


def test_text_token_redaction():
    text = redact_text("Authorization: Bearer abcdefghijklmnop token=hello-world")
    assert "abcdefghijklmnop" not in text
    assert "hello-world" not in text

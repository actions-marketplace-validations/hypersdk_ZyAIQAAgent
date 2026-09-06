# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
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


def test_redact_stops_at_max_depth():
    nested: dict = {"leaf": "value"}
    for _ in range(5):
        nested = {"child": nested}
    assert redact(nested, max_depth=2) == {"child": {"child": {"child": "<max-depth>"}}}


def test_redact_handles_tuples():
    clean = redact(({"token": "abc"}, "safe"))
    assert clean == ({"token": REDACTED}, "safe")


def test_redact_handles_sets():
    clean = redact({"safe-one", "safe-two"})
    assert clean == {"safe-one", "safe-two"}


def test_redact_leaves_unknown_types_unchanged():
    assert redact(42) == 42
    assert redact(None) is None
    assert redact(3.14) == 3.14

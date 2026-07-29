"""Unit tests for the flow-journey parser (agents/flow/parse.py)."""

from __future__ import annotations

from agents.flow.parse import parse_flow, parse_prose_heuristic, parse_step_lines


def _actions(steps):
    return [s["action"] for s in steps]


def test_step_lines_basic_verbs():
    steps = parse_step_lines('go to /\nclick "Products"\nfill email = a@b.com\npress Enter\nwait 500\nassert "Hi"')
    assert _actions(steps) == ["goto", "click", "fill", "press", "wait", "assert"]
    assert steps[0]["target"] == "/"
    assert steps[1]["target"] == "Products"
    assert steps[2]["target"] == "email" and steps[2]["value"] == "a@b.com"
    assert steps[3]["value"] == "Enter"
    assert steps[5]["assertion"] == "Hi"


def test_go_to_with_space_is_goto():
    steps, mode = parse_flow('go to /pricing\nassert "Pro"')
    assert mode == "steps"
    assert steps[0]["action"] == "goto" and steps[0]["target"] == "/pricing"


def test_negative_assertion():
    steps = parse_step_lines('assert not "spinner"')
    assert steps[0]["action"] == "assert_not"
    assert steps[0]["assertion"] == "spinner"


def test_assert_count_and_value():
    steps = parse_step_lines("assert count .card = 3\nassert value email = qa@x.com")
    assert steps[0]["action"] == "assert_count"
    assert steps[0]["target"] == ".card" and steps[0]["value"] == "3"
    assert steps[1]["action"] == "assert_value"
    assert steps[1]["target"] == "email" and steps[1]["value"] == "qa@x.com"


def test_bare_line_is_assertion():
    steps = parse_step_lines("HyperSDK is visible")
    assert steps[0]["action"] == "assert"
    assert "HyperSDK" in steps[0]["assertion"]


def test_prose_heuristic_splits_and_detects_goto():
    steps = parse_prose_heuristic("Go to /products, click Pricing, then verify the Pro plan")
    acts = _actions(steps)
    assert acts[0] == "goto"
    assert "click" in acts
    assert "assert" in acts


def test_prose_heuristic_negative():
    steps = parse_prose_heuristic("go to / and the error should not be visible")
    assert any(s["action"] == "assert_not" for s in steps)


def test_prose_inserts_leading_goto():
    steps = parse_prose_heuristic("click Login then verify dashboard")
    assert steps[0]["action"] == "goto"


def test_empty_raises():
    import pytest

    with pytest.raises(ValueError):
        parse_flow("   ")


def test_steps_mode_forces_line_parser():
    # a single line that isn't clearly a verb-list still parses as steps when forced
    steps, mode = parse_flow("HyperSDK", steps_mode=True)
    assert mode == "steps"
    assert steps[0]["action"] == "assert"


def test_new_flow_actions():
    steps = parse_step_lines(
        "\n".join(
            [
                "hover Menu",
                'select region = us-east',
                "upload file = /tmp/a.iso",
                'download "Export" to /tmp/out.csv',
                "dialog accept Confirm delete",
                "iframe #embed",
                'drag "Card A" to "Column B"',
                "clock install",
                "clock set:2025-06-01T12:00:00Z",
                "clock fastForward:5000",
                'wait until "Running" 20000ms',
                "assert url /vms",
                "assert api /api/vms = 200",
                'assert aria body = - heading "VMs"',
                "iframe off",
            ]
        )
    )
    assert _actions(steps) == [
        "hover",
        "select",
        "upload",
        "download",
        "dialog",
        "iframe",
        "drag",
        "clock",
        "clock",
        "clock",
        "wait_until",
        "assert_url",
        "assert_api",
        "assert_aria",
        "iframe",
    ]
    assert steps[1]["target"] == "region" and steps[1]["value"] == "us-east"
    assert steps[2]["value"] == "/tmp/a.iso"
    assert steps[4]["value"] == "accept"
    assert steps[5]["target"] == "#embed"
    assert steps[-1]["target"] == ""
    assert steps[11]["assertion"] == "/vms"
    assert steps[12]["target"] == "/api/vms" and steps[12]["value"] == "200"

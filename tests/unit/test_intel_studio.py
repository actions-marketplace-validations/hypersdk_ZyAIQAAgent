# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0

from orchestrator.intelligence.studio import build_studio


def test_studio_classifies_failed_case_and_points_at_primary(tmp_path):
    video = tmp_path / "reports" / "videos" / "login.webm"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"not-a-real-webm")
    job = {
        "id": "job-1",
        "kind": "smoke",
        "status": "failed",
        "finished_at": "2026-09-07T00:00:00+00:00",
        "result": {
            "cases": [
                {
                    "title": "login works",
                    "status": "failed",
                    "error": "Timeout exceeded while waiting for locator('button')",
                    "hint": "selector drifted",
                    "video": "reports/videos/login.webm",
                    "trace": None,
                    "console_logs": ["[error] boom"],
                    "network_errors": [],
                },
                {"title": "home loads", "status": "passed", "error": ""},
            ]
        },
    }
    studio = build_studio(job, repo=tmp_path)
    assert studio["failed_count"] == 1
    assert studio["total_count"] == 2
    assert studio["primary"]["title"] == "login works"
    assert studio["primary"]["category"] == "selector"
    assert studio["primary"]["video_present"] is True
    assert studio["cases"][1]["category"] == "healthy"


def test_studio_404_shaped_when_no_cases():
    studio = build_studio({"id": "job-2", "kind": "ping", "status": "succeeded", "result": {}})
    assert studio["cases"] == []
    assert studio["primary"] is None

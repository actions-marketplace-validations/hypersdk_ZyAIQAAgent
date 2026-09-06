# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for fetch_requirements' `document` source branch — a real,
non-GitHub requirements source reusing knowledge/documents.py's existing
multi-format text extraction (md/txt/pdf/etc.) instead of a second parser."""

from __future__ import annotations

from orchestrator.nodes.fetch import fetch_requirements


def test_document_source_reads_markdown_file(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text(
        "# Login page loads\n\n## Acceptance Criteria\n1. Navigate to `/login`\n",
        encoding="utf-8",
    )

    result = fetch_requirements({"source": "document", "document_paths": [str(doc)]})

    assert result.get("error") is None
    assert len(result["spec_contents"]) == 1
    assert "Login page loads" in result["spec_contents"][0]
    assert result["spec_paths"] == [str(doc)]


def test_document_source_requires_at_least_one_path():
    result = fetch_requirements({"source": "document", "document_paths": []})
    assert "document_paths" in result["error"]


def test_document_source_records_missing_file_without_failing_the_run(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text("# A real spec\n", encoding="utf-8")
    missing = tmp_path / "does-not-exist.md"

    result = fetch_requirements(
        {"source": "document", "document_paths": [str(doc), str(missing)]}
    )

    assert result.get("error") is None
    assert len(result["spec_contents"]) == 1
    assert any("not found" in msg for msg in result["metadata"]["document_errors"])


def test_document_source_rejects_unsupported_file_type(tmp_path):
    doc = tmp_path / "spec.exe"
    doc.write_bytes(b"\x00\x01")

    result = fetch_requirements({"source": "document", "document_paths": [str(doc)]})

    assert result.get("error") is None
    assert result["spec_contents"] == []
    assert any("unsupported" in msg for msg in result["metadata"]["document_errors"])

#!/usr/bin/env python3
# Copyright 2026 ZyvorAI Labs Private Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Validate Kubernetes manifest files without a running cluster."""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_KEYS = ("apiVersion:", "kind:", "metadata:")

MANIFESTS = [
    "kubernetes/configmap.yaml",
    "kubernetes/secret.yaml",
    "kubernetes/rbac.yaml",
    "kubernetes/pvc.yaml",
    "kubernetes/deployment.yaml",
    "kubernetes/service.yaml",
    "kubernetes/cronjob.yaml",
    "kubernetes/ingress.yaml",
]


def validate_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{path}: file not found"]
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return [f"{path}: file is empty"]
    for key in REQUIRED_KEYS:
        if key not in text:
            errors.append(f"{path}: missing '{key.rstrip(':')}'")
    return errors


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    all_errors: list[str] = []

    for rel in MANIFESTS:
        all_errors.extend(validate_manifest(repo / rel))

    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"All {len(MANIFESTS)} Kubernetes manifests passed offline validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

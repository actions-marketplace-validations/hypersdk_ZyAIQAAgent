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

"""Convert Playwright codegen JS/TS output into Zyvor flow steps."""

from __future__ import annotations

import re
from typing import Any


def _step(action: str, target: str = "", value: str = "", assertion: str = "") -> dict[str, Any]:
    return {"action": action, "target": target, "value": value, "assertion": assertion}


def _str_lit(m: re.Match[str], *groups: int) -> str:
    for g in groups:
        val = m.group(g)
        if val and val not in "\"'`":
            return val
    return ""


def import_codegen(script: str) -> list[dict[str, Any]]:
    """Parse a Playwright codegen (or hand-written) script into flow steps."""
    text = script or ""
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    found: list[tuple[int, dict[str, Any]]] = []

    def add(pos: int, step: dict[str, Any]) -> None:
        found.append((pos, step))

    for m in re.finditer(r"\.goto\(\s*(['\"`])(.*?)\1", text):
        add(m.start(), _step("goto", m.group(2)))

    for m in re.finditer(
        r"\.getByRole\(\s*['\"](?:button|link)['\"]\s*,\s*\{\s*name:\s*"
        r"(?:/([^/]+)/[a-z]*|(['\"`])(.*?)\2)\s*\}\s*\)(?:\.first\(\))?\s*\.click\(",
        text,
        re.I,
    ):
        add(m.start(), _step("click", _str_lit(m, 1, 3)))

    for m in re.finditer(
        r"\.getByText\(\s*(?:/([^/]+)/[a-z]*|(['\"`])(.*?)\2)\s*\)(?:\.first\(\))?\s*\.click\(",
        text,
        re.I,
    ):
        add(m.start(), _step("click", _str_lit(m, 1, 3)))

    for m in re.finditer(
        r"\.(?:getByLabel|getByPlaceholder)\(\s*(?:/([^/]+)/[a-z]*|(['\"`])(.*?)\2)\s*\)"
        r"(?:\.first\(\))?\s*\.fill\(\s*(['\"`])(.*?)\4\s*\)",
        text,
        re.I,
    ):
        add(m.start(), _step("fill", _str_lit(m, 1, 3), m.group(5)))

    for m in re.finditer(
        r"\.locator\(\s*(['\"`])(.*?)\1\s*\)(?:\.first\(\))?\s*\.fill\(\s*(['\"`])(.*?)\3\s*\)",
        text,
        re.I,
    ):
        add(m.start(), _step("fill", m.group(2), m.group(4)))

    for m in re.finditer(
        r"\.(?:getByLabel|locator)\(\s*(?:/([^/]+)/[a-z]*|(['\"`])(.*?)\2)\s*\)"
        r"(?:\.first\(\))?\s*\.selectOption\(\s*(?:\{\s*label:\s*(['\"`])(.*?)\4\s*\}|(['\"`])(.*?)\6)\s*\)",
        text,
        re.I,
    ):
        add(m.start(), _step("select", _str_lit(m, 1, 3), m.group(5) or m.group(7) or ""))

    for m in re.finditer(r"\.press\(\s*(['\"`])(.*?)\1\s*\)", text):
        add(m.start(), _step("press", value=m.group(2)))

    for m in re.finditer(
        r"expect\(.*?getByText\(\s*(?:/([^/]+)/[a-z]*|(['\"`])(.*?)\2)\s*\)",
        text,
        re.I | re.S,
    ):
        label = _str_lit(m, 1, 3)
        if label:
            add(m.start(), _step("assert", assertion=label))

    for m in re.finditer(r"toHaveURL\(\s*(?:/([^/]+)/[a-z]*|(['\"`])(.*?)\2)\s*\)", text):
        add(m.start(), _step("assert_url", assertion=_str_lit(m, 1, 3)))

    for m in re.finditer(
        r"\.locator\(\s*(['\"`])(.*?)\1\s*\)(?:\.first\(\))?\s*\.click\(",
        text,
    ):
        add(m.start(), _step("click", m.group(2)))

    found.sort(key=lambda x: x[0])
    deduped: list[dict[str, Any]] = []
    for _, s in found:
        if deduped and deduped[-1] == s:
            continue
        deduped.append(s)

    if not deduped:
        raise ValueError("no Playwright actions found in script (expected page.goto / click / fill)")
    return deduped

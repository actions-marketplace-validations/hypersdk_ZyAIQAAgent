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

"""Exercise the JSON-Schema validator (playwright/scripts/lib/schema-validate.mjs)
via node, so the hand-rolled OpenAPI-subset validator has real coverage."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "playwright" / "scripts" / "lib" / "schema-validate.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")


def _validate(schema: dict, data, root: dict | None = None) -> list[str]:
    """Run the JS validator and return its error list."""
    root = root if root is not None else schema
    harness = (
        f"import {{ validate }} from '{LIB.as_posix()}';\n"
        f"const schema = {json.dumps(schema)};\n"
        f"const data = {json.dumps(data)};\n"
        f"const root = {json.dumps(root)};\n"
        "process.stdout.write(JSON.stringify(validate(schema, data, root)));\n"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", harness],
                         capture_output=True, text=True, cwd=REPO)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_valid_object_passes():
    schema = {"type": "object", "required": ["id", "name"],
              "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}
    assert _validate(schema, {"id": 1, "name": "vm"}) == []


def test_missing_required_property():
    schema = {"type": "object", "required": ["id", "email"], "properties": {"id": {"type": "integer"}}}
    errs = _validate(schema, {"id": 1})
    assert any("email" in e and "required" in e for e in errs)


def test_required_enforced_without_properties():
    # regression: `required` must be checked even when the schema has no `properties`
    errs = _validate({"type": "object", "required": ["NOPE"]}, {"id": 1, "name": "x"})
    assert any("NOPE" in e and "required" in e for e in errs)


def test_wrong_type():
    schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
    errs = _validate(schema, {"count": "five"})
    assert any("count" in e and "integer" in e for e in errs)


def test_integer_accepted_as_number():
    assert _validate({"type": "number"}, 3) == []


def test_ref_resolution():
    root = {"components": {"schemas": {"Post": {"type": "object", "required": ["title"],
            "properties": {"title": {"type": "string"}}}}}}
    schema = {"$ref": "#/components/schemas/Post"}
    assert _validate(schema, {"title": "hi"}, root) == []
    assert _validate(schema, {}, root)  # missing title → error


def test_unresolved_ref_reported():
    errs = _validate({"$ref": "#/components/schemas/Nope"}, {}, {"components": {"schemas": {}}})
    assert any("unresolved $ref" in e for e in errs)


def test_nullable_allows_null():
    assert _validate({"type": "string", "nullable": True}, None) == []
    assert _validate({"type": "string"}, None)  # non-nullable null → error


def test_enum():
    schema = {"type": "string", "enum": ["running", "stopped"]}
    assert _validate(schema, "running") == []
    assert _validate(schema, "paused")


def test_array_items():
    schema = {"type": "array", "items": {"type": "integer"}}
    assert _validate(schema, [1, 2, 3]) == []
    assert _validate(schema, [1, "two"])


def test_oneof():
    schema = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
    assert _validate(schema, "hi") == []
    assert _validate(schema, 5) == []
    assert _validate(schema, {"x": 1})  # matches neither → error


def test_nested_object_error_path():
    schema = {"type": "object", "properties": {"user": {"type": "object",
              "required": ["email"], "properties": {"email": {"type": "string"}}}}}
    errs = _validate(schema, {"user": {}})
    assert any("user" in e and "email" in e for e in errs)

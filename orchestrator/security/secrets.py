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

"""Secret references for durable schedules and queued jobs.

Persistent records must contain references, never raw credentials.
Supported references:

    {"$secret": "env:OPENAI_API_KEY"}
    {"$secret": "file:/var/run/secrets/zyvor/token"}
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from orchestrator.security.redaction import is_secret_key


class SecretReferenceError(ValueError):
    pass


def is_secret_ref(value: Any) -> bool:
    return isinstance(value, Mapping) and set(value) == {"$secret"} and isinstance(value["$secret"], str)


def assert_persistable(value: Any, *, parent_key: str = "", path: str = "$", depth: int = 0) -> None:
    if depth > 20:
        raise SecretReferenceError(f"{path}: value is too deeply nested")
    if is_secret_key(parent_key) and value not in (None, "", [], {}):
        if not is_secret_ref(value):
            raise SecretReferenceError(
                f"{path}: raw secret values cannot be persisted; use {{\"$secret\":\"env:NAME\"}}"
            )
        _validate_ref(value["$secret"], path)
        return
    if isinstance(value, Mapping):
        if is_secret_ref(value):
            _validate_ref(value["$secret"], path)
            return
        for key, item in value.items():
            assert_persistable(item, parent_key=str(key), path=f"{path}.{key}", depth=depth + 1)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            assert_persistable(item, parent_key=parent_key, path=f"{path}[{index}]", depth=depth + 1)


def _validate_ref(ref: str, path: str) -> None:
    if ref.startswith("env:") and len(ref) > 4:
        return
    if ref.startswith("file:/") and len(ref) > 6:
        return
    raise SecretReferenceError(f"{path}: unsupported secret reference {ref!r}")


def resolve_secret_refs(value: Any, *, depth: int = 0) -> Any:
    if depth > 20:
        raise SecretReferenceError("secret reference tree is too deeply nested")
    if is_secret_ref(value):
        return resolve_secret(value["$secret"])
    if isinstance(value, Mapping):
        return {k: resolve_secret_refs(v, depth=depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_secret_refs(v, depth=depth + 1) for v in value]
    if isinstance(value, tuple):
        return tuple(resolve_secret_refs(v, depth=depth + 1) for v in value)
    return value


def resolve_secret(ref: str) -> str:
    _validate_ref(ref, "$")
    if ref.startswith("env:"):
        name = ref[4:]
        if name not in os.environ:
            raise SecretReferenceError(f"environment secret {name!r} is not configured")
        return os.environ[name]
    path = Path(ref[5:])
    try:
        stat = path.stat()
    except OSError as exc:
        raise SecretReferenceError(f"secret file is unavailable: {path}") from exc
    if stat.st_size > 64 * 1024:
        raise SecretReferenceError("secret file is unexpectedly large")
    return path.read_text(encoding="utf-8").rstrip("\r\n")

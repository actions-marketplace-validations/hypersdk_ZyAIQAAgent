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

import pytest

from orchestrator.security.secrets import SecretReferenceError, assert_persistable, resolve_secret_refs


def test_raw_secret_rejected():
    with pytest.raises(SecretReferenceError):
        assert_persistable({"auth": {"token": "raw-token"}})


def test_env_secret_reference(monkeypatch):
    monkeypatch.setenv("QA_TOKEN", "secret-value")
    value = {"auth": {"token": {"$secret": "env:QA_TOKEN"}}}
    assert_persistable(value)
    assert resolve_secret_refs(value)["auth"]["token"] == "secret-value"

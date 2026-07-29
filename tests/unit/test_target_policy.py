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

import ipaddress

import pytest

from orchestrator.security.target_policy import TargetPolicy, TargetPolicyError


def test_blocks_metadata_ip():
    policy = TargetPolicy(resolve_dns=False)
    with pytest.raises(TargetPolicyError):
        policy._validate_ip(ipaddress.ip_address("169.254.169.254"), host_allowed=True)


def test_blocks_private_by_default():
    policy = TargetPolicy(allow_private=False, resolve_dns=False)
    with pytest.raises(TargetPolicyError):
        policy._validate_ip(ipaddress.ip_address("127.0.0.1"), host_allowed=True)


def test_host_allowlist():
    policy = TargetPolicy(allowed_hosts=("*.zyvor.dev", "zyvor.dev"), resolve_dns=False)
    assert policy.validate_url("https://qa.zyvor.dev/path#fragment") == "https://qa.zyvor.dev/path"
    with pytest.raises(TargetPolicyError):
        policy.validate_url("https://example.org/")


def test_userinfo_is_rejected():
    policy = TargetPolicy(resolve_dns=False)
    with pytest.raises(TargetPolicyError):
        policy.validate_url("https://user:pass@example.org/")


def test_custom_tls_port_uses_https_policy():
    policy = TargetPolicy(allowed_ports=(24631,), allow_http=False, resolve_dns=False)
    assert policy.validate_host("forge.zyvor.dev", 24631) == "forge.zyvor.dev"

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

import pytest
from fastapi import HTTPException

from knowledge.security import ACCESS_PATTERN, TENANT_PATTERN, _validate_levels


def test_tenant_pattern() -> None:
    assert TENANT_PATTERN.fullmatch("acme-prod_01")
    assert not TENANT_PATTERN.fullmatch("../other-tenant")
    assert not TENANT_PATTERN.fullmatch("tenant with spaces")


def test_access_pattern() -> None:
    assert ACCESS_PATTERN.fullmatch("customer")
    assert ACCESS_PATTERN.fullmatch("support_engineer")
    assert not ACCESS_PATTERN.fullmatch("Admin Root")


def test_empty_access_levels_are_rejected() -> None:
    with pytest.raises(HTTPException):
        _validate_levels(())

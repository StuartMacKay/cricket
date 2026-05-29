"""Shared fixtures for the API test suite."""

import pytest

from api.models import APIKey
from tests.factories import SiteFactory


@pytest.fixture
def api_key(db):
    """A valid API key with access to all sites."""
    key_obj = APIKey.objects.create(name="test-agent")
    return key_obj, key_obj.key


@pytest.fixture
def admin_api_key(db):
    """An admin API key."""
    key_obj = APIKey.objects.create(name="test-admin", is_admin=True)
    return key_obj, key_obj.key


@pytest.fixture
def auth_client(client, api_key):
    """Django test client pre-configured with the API bearer token."""
    _, plaintext = api_key
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {plaintext}"
    return client


@pytest.fixture
def admin_auth_client(client, admin_api_key):
    """Django test client pre-configured with an admin API bearer token."""
    _, plaintext = admin_api_key
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {plaintext}"
    return client

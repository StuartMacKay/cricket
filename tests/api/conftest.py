"""Shared fixtures for the api test suite."""

import pytest
from api.models import APIKey


@pytest.fixture
def api_key(db):
    """A valid API key with access to all sites."""
    key_obj = APIKey.objects.create(name="test-agent")
    return key_obj, key_obj.key


@pytest.fixture
def auth_client(client, api_key):
    """Django test client pre-configured with the API bearer token."""
    _, plaintext = api_key
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {plaintext}"
    return client

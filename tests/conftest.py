from django.core.management import call_command

import pytest


@pytest.fixture(autouse=True)
def use_dummy_cache_backend(settings):
    """Disable caching when running the tests"""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    """All files uploaded during testing are saved in the tmp directory.
    That way there is no need to clean up afterwards."""
    settings.MEDIA_ROOT = tmpdir.strpath



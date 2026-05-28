"""
Integration tests for node/src/lighthouse.js.

These tests run the script for real (Chrome/Chromium required) and inspect
the ``configSettings`` block that Lighthouse embeds in every report to verify
that the correct emulation and throttling profile was applied.

Key fields checked
------------------
configSettings.formFactor        'mobile' | 'desktop'
configSettings.throttlingMethod  'simulate' (throttled) | 'provided' (none)
configSettings.screenEmulation   includes mobile: true/false and viewport dims

Marked ``integration`` so they are skipped by default (they take ~10–30 s each).
Run explicitly with::

    pytest -m integration tests/node/
"""

import json
import os
import subprocess
import tempfile

import pytest
from django.conf import settings

pytestmark = pytest.mark.integration

LIGHTHOUSE_JS = os.path.join(settings.NODE_DIR, "src", "lighthouse.js")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_lighthouse(url: str, flags: dict | None = None) -> dict:
    """Run lighthouse.js against *url*, optionally with a flags file.

    Returns the parsed Lighthouse Result (LHR) dict, or raises
    AssertionError if the script exits with a non-zero status.
    """
    cmd = ["node", LIGHTHOUSE_JS, url]

    if flags:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            json.dump(flags, fp)
            flags_path = fp.name
        cmd.append(f"--cli-flags-path={flags_path}")
    else:
        flags_path = None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
        )
    finally:
        if flags_path:
            os.unlink(flags_path)

    assert result.returncode == 0, (
        f"lighthouse.js exited {result.returncode}:\n"
        + result.stderr.decode(errors="replace")
    )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def page_url(make_httpserver):
    """A minimal HTML page served by a module-scoped local HTTP server.

    Uses ``make_httpserver`` (not ``httpserver``) so the server lifetime
    matches the module scope and can be shared across all three test classes,
    giving us only three Lighthouse runs total (one per profile).
    """
    server = make_httpserver
    html = b"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Lighthouse integration test page">
  <title>Lighthouse Test</title>
</head>
<body><h1>Lighthouse integration test</h1></body>
</html>"""
    server.expect_request("/").respond_with_data(html, content_type="text/html")
    return server.url_for("/")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDefaultMobileProfile:
    """No flags → Lighthouse runs with its built-in mobile defaults."""

    @pytest.fixture(scope="class")
    def lhr(self, page_url):
        return run_lighthouse(page_url)

    def test_form_factor_is_mobile(self, lhr):
        assert lhr["configSettings"]["formFactor"] == "mobile"

    def test_throttling_method_is_simulate(self, lhr):
        assert lhr["configSettings"]["throttlingMethod"] == "simulate"

    def test_network_rtt_is_mobile(self, lhr):
        # Mobile preset: 150 ms RTT (slow 4G simulation)
        assert lhr["configSettings"]["throttling"]["rttMs"] == 150

    def test_screen_emulation_is_mobile(self, lhr):
        assert lhr["configSettings"]["screenEmulation"]["mobile"] is True

    def test_viewport_is_mobile_sized(self, lhr):
        emulation = lhr["configSettings"]["screenEmulation"]
        # Moto G Power: 412 px wide
        assert emulation["width"] == 412

    def test_cpu_slowdown_is_applied(self, lhr):
        # Mobile: 4× CPU throttle
        assert lhr["configSettings"]["throttling"]["cpuSlowdownMultiplier"] == 4


class TestExplicitMobileFlag:
    """{"formFactor": "mobile"} → same profile as no flags at all."""

    @pytest.fixture(scope="class")
    def lhr(self, page_url):
        return run_lighthouse(page_url, flags={"formFactor": "mobile"})

    def test_form_factor_is_mobile(self, lhr):
        assert lhr["configSettings"]["formFactor"] == "mobile"

    def test_throttling_method_is_simulate(self, lhr):
        assert lhr["configSettings"]["throttlingMethod"] == "simulate"

    def test_network_rtt_is_mobile(self, lhr):
        assert lhr["configSettings"]["throttling"]["rttMs"] == 150

    def test_screen_emulation_is_mobile(self, lhr):
        assert lhr["configSettings"]["screenEmulation"]["mobile"] is True

    def test_cpu_slowdown_is_applied(self, lhr):
        assert lhr["configSettings"]["throttling"]["cpuSlowdownMultiplier"] == 4


class TestDesktopProfile:
    """{"formFactor": "desktop"} → desktop preset, no throttling."""

    @pytest.fixture(scope="class")
    def lhr(self, page_url):
        return run_lighthouse(page_url, flags={"formFactor": "desktop"})

    def test_form_factor_is_desktop(self, lhr):
        assert lhr["configSettings"]["formFactor"] == "desktop"

    def test_network_rtt_is_lower_than_mobile(self, lhr):
        # Desktop preset: 40 ms RTT (vs 150 ms for mobile) — lighter throttle
        assert lhr["configSettings"]["throttling"]["rttMs"] == 40

    def test_screen_emulation_is_not_mobile(self, lhr):
        assert lhr["configSettings"]["screenEmulation"]["mobile"] is False

    def test_viewport_is_desktop_sized(self, lhr):
        emulation = lhr["configSettings"]["screenEmulation"]
        assert emulation["width"] == 1350

    def test_cpu_slowdown_is_not_applied(self, lhr):
        # Desktop preset: 1× (no slowdown)
        assert lhr["configSettings"]["throttling"]["cpuSlowdownMultiplier"] == 1

"""Reproduce exact test conditions including django_db marker."""
import subprocess
import os
import pytest
import plotly.graph_objects as go
import plotly.io as pio
from werkzeug import Response

pytestmark = pytest.mark.django_db

NODE_DIR = '/app/node'
LIGHTHOUSE_SCRIPT = os.path.join(NODE_DIR, 'src', 'lighthouse.js')


def test_kaleido_after_lighthouse_with_db(httpserver):
    """Simulate exactly what test_site_snapshot does."""
    httpserver.expect_request('/').respond_with_data(
        b'<html><head><meta charset=utf-8><title>T</title><meta name=viewport content="width=device-width"></head><body><h1>T</h1></body></html>',
        mimetype='text/html',
    )
    httpserver.expect_request('/about/').respond_with_response(
        Response('Not Found', status=404)
    )

    r1 = subprocess.run(
        [LIGHTHOUSE_SCRIPT, httpserver.url_for('/'), '--quiet'],
        capture_output=True, timeout=120
    )
    print(f'\nLighthouse 1 exit: {r1.returncode}')

    r2 = subprocess.run(
        [LIGHTHOUSE_SCRIPT, httpserver.url_for('/about/'), '--quiet'],
        capture_output=True, timeout=120
    )
    print(f'Lighthouse 2 exit: {r2.returncode}')

    fig = go.Figure(data=[go.Bar(x=[1,2,3], y=[1,2,3])])
    try:
        svg = pio.to_image(fig, format='svg')
        print(f'kaleido OK: {len(svg)} bytes')
    except Exception as e:
        pytest.fail(f'kaleido FAILED: {e}')

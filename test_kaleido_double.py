import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import pytest
import plotly.graph_objects as go
import plotly.io as pio
from pytest_httpserver import HTTPServer as WSGIServer
from werkzeug import Response

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

NODE_DIR = '/app/node'
LIGHTHOUSE_SCRIPT = os.path.join(NODE_DIR, 'src', 'lighthouse.js')

def test_kaleido_after_two_lighthouses(httpserver):
    """Simulate what test_site_snapshot does: 2 lighthouse audits then kaleido."""
    # Configure httpserver like test_site_snapshot does
    httpserver.expect_request('/').respond_with_data(
        b'<html><head><meta charset=utf-8><title>T</title><meta name=viewport content="width=device-width"></head><body><h1>T</h1></body></html>',
        mimetype='text/html',
    )
    httpserver.expect_request('/about/').respond_with_response(
        Response('Not Found', status=404)
    )

    # Run lighthouse on the page (success)
    result1 = subprocess.run(
        [LIGHTHOUSE_SCRIPT, httpserver.url_for('/'), '--quiet'],
        capture_output=True, timeout=120
    )
    print(f'\nLighthouse 1 exit: {result1.returncode}, output: {len(result1.stdout)} bytes')

    # Run lighthouse on 404 page (failure, like /about/)
    result2 = subprocess.run(
        [LIGHTHOUSE_SCRIPT, httpserver.url_for('/about/'), '--quiet'],
        capture_output=True, timeout=120
    )
    print(f'Lighthouse 2 exit: {result2.returncode}')

    # Now try kaleido
    fig = go.Figure(data=[go.Bar(x=[1,2,3], y=[1,2,3])])
    try:
        svg = pio.to_image(fig, format='svg')
        print(f'kaleido OK: {len(svg)} bytes')
    except Exception as e:
        pytest.fail(f'kaleido FAILED: {e}')

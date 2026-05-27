import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import django
import pytest

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from django.conf import settings

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><head><meta charset=utf-8><title>T</title><meta name=viewport content="width=device-width"></head><body><h1>T</h1></body></html>')
    def log_message(self, *a): pass

def test_kaleido_after_lighthouse():
    server = HTTPServer(('127.0.0.1', 19998), Handler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    LIGHTHOUSE_SCRIPT = os.path.join(settings.NODE_DIR, 'src', 'lighthouse.js')
    result = subprocess.run([LIGHTHOUSE_SCRIPT, 'http://127.0.0.1:19998/', '--quiet'], capture_output=True, timeout=120)
    assert result.returncode == 0, f"Lighthouse failed: {result.stderr[:200]}"
    server.shutdown()

    import plotly.graph_objects as go
    import plotly.io as pio
    fig = go.Figure(data=[go.Bar(x=[1,2,3], y=[1,2,3])])
    svg = pio.to_image(fig, format='svg')
    assert len(svg) > 0

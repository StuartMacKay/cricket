"""Test with Celery eager mode and actual tasks."""
import pytest
from werkzeug import Response

pytestmark = pytest.mark.django_db

from metrics import tasks
from config.celery import app
from tests.factories import SiteFactory


def test_kaleido_with_celery_tasks(httpserver):
    app.conf.task_always_eager = True

    httpserver.expect_request('/sitemap.xml').respond_with_data(
        b'''<?xml version="1.0" encoding="utf-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>''' + httpserver.url_for('/').encode() + b'''</loc></url>
        <url><loc>''' + httpserver.url_for('/about/').encode() + b'''</loc></url>
        </urlset>''',
        mimetype='text/xml',
    )
    httpserver.expect_request('/').respond_with_data(
        b'<html><head><meta charset=utf-8><title>T</title><meta name=viewport content="width=device-width"></head><body><h1>T</h1></body></html>',
        mimetype='text/html',
    )
    httpserver.expect_request('/about/').respond_with_response(
        Response('Not Found', status=404)
    )

    site = SiteFactory(
        sitemap_url=httpserver.url_for('/sitemap.xml'),
        config={'formFactor': 'desktop'},
    )

    tasks.take_snapshot(site.pk)

    snapshot = site.snapshots.first()
    pages = snapshot.pages.all()
    print(f'\nPages: {pages.count()}, audited: {pages.filter(audited=True).count()}')
    assert pages.count() == 2
    assert pages.filter(audited=True).count() == 1

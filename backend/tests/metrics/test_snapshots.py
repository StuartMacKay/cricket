import os

from django.template import Context, Template

import filetype
import pytest
from werkzeug import Response

from metrics import tasks
from project.celery import app
from tests.factories import SiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def urls():
    return [
        "http://127.0.0.1:8000/",
        "http://127.0.0.1:8000/about/",
    ]


@pytest.fixture
def sitemap(urls) -> bytes:
    text = """<?xml version="1.0" encoding="utf-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {% for url in urls %}<url><loc>{{ url }}</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority></url>{% endfor %}
    </urlset>
    """
    template = Template(text)
    context = Context({"urls": [str(url) for url in urls]})
    return template.render(context).encode()


@pytest.fixture
def page() -> bytes:
    return b"""<!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="description" content="Site for testing">
      <meta name="author" content="Stuart MacKay">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Integration Test</title>
    </head>
    <body>
    <h1>Integration Test</h1>
    <p>Lorem ipsum dolor sit</p>
    </body>
    </html>
    """


def test_site_snapshot(caplog, httpserver, urls, sitemap, page):
    # This is a mammoth test in which entire cycle of creating a snapshot
    # and generating a PDF report is run - which is why the sitemap only
    # has two URLs. One URL returns 404 to check whether the report gets
    # published even though not all Pages were audited. Celery is run in
    # eager mode as we are only interested in the outcome of the tasks,
    # not whether they run correctly.
    app.conf.task_always_eager = True

    httpserver.expect_request("/sitemap.xml").respond_with_data(
        sitemap,
        mimetype="text/xml",
    )
    httpserver.expect_request("/").respond_with_data(
        page,
        mimetype="text/html",
    )

    httpserver.expect_request("/about/").respond_with_response(
        Response("Not Found", status=404)
    )

    site = SiteFactory(
        sitemap_url="http:localhost:8000/sitemap.xml",
        config_file__data=b'{"formFactor": "desktop"}',
    )

    # Generate the site snapshot and publish the report
    tasks.take_snapshot(site.pk)

    # A Page is generated for every URL in the Sitemap
    snapshot = site.snapshots.first()
    pages = snapshot.pages.all()

    assert pages.count() == 2
    assert pages.filter(audited=True).count() == 1
    assert pages.filter(audited=False).count() == 1

    # Each Page has a Lighthouse report
    for page in pages:
        path = page.report.path
        assert os.path.exists(path)
        assert os.path.getsize(path) != 0

    # Data was extracted for each page that was successfully audited
    for page in pages.filter(audited=True):
        for key, category in page.data["categories"].items():
            assert "rating" in category
            assert "score" in category
        for key, audit in page.data["audits"].items():
            assert "rating" in audit
            assert "score" in audit

    # Data was not extracted from pages where the audit failed
    for page in pages.filter(audited=False):
        assert page.data == {}

    # The snapshot contains the configuration used by Lighthouse
    assert "config" in snapshot.data
    assert "formFactor" in snapshot.data["config"]

    # The snapshot contains metrics extracted the page data
    for key, category in snapshot.data["categories"].items():
        assert "id" in category
        assert "title" in category
        assert "ratings" in category
        assert "scores" in category
        assert "urls" in category

    for key, audit in snapshot.data["audits"].items():
        assert "id" in audit
        assert "title" in audit
        assert "ratings" in audit
        assert "scores" in audit
        assert "urls" in audit

    # The snapshot contains the PDF report
    path = snapshot.report.path
    assert os.path.exists(path)
    assert os.path.getsize(path) != 0
    kind = filetype.guess(path)
    assert kind.extension == "pdf"
    assert kind.mime == "application/pdf"

    # Check logging (the fetching of the sitemaps was covered in test_snapshots)
    assert "Page audit started" in caplog.text
    assert "Page was audited" in caplog.text
    assert "Page was not audited" in caplog.text

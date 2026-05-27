import zlib

from django.template import Context, Template

import pytest
import requests
from pydantic import HttpUrl

from tests.factories import SiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def urls():
    return [
        HttpUrl("http://127.0.0.1:8000/"),
        HttpUrl("http://127.0.0.1:8000/page1/"),
        HttpUrl("http://127.0.0.1:8000/page2/"),
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
def compressed_sitemap(sitemap) -> bytes:
    return zlib.compress(sitemap, wbits=16 + zlib.MAX_WBITS)


@pytest.fixture
def siteindex(httpserver) -> bytes:
    sitemap_url = httpserver.url_for("/sitemap.xml")
    return f"""<sitemapindex>
    <sitemap>
    <loc>{sitemap_url}</loc>
    </sitemap>
    </sitemapindex>
    """.encode()


def test_sitemap_url(httpserver, sitemap, urls):
    httpserver.expect_request("/sitemap.xml").respond_with_data(sitemap)
    site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
    actual = list(site.get_urls())
    for url in urls:
        assert url in actual


def test_siteindex(httpserver, siteindex, sitemap, urls):
    httpserver.expect_request("/siteindex.xml").respond_with_data(siteindex)
    httpserver.expect_request("/sitemap.xml").respond_with_data(sitemap)
    site = SiteFactory(sitemap_url=httpserver.url_for("/siteindex.xml"))
    actual = list(site.get_urls())
    for url in urls:
        assert url in actual


def test_compressed_sitemap(httpserver, compressed_sitemap, urls):
    httpserver.expect_request("/sitemap.xml.gz").respond_with_data(compressed_sitemap)
    site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml.gz"))
    actual = list(site.get_urls())
    for url in urls:
        assert url in actual


def test_network_error(caplog, monkeypatch):
    def mock_return(*args) -> bytes:  # noqa
        raise requests.RequestException()

    monkeypatch.setattr(requests, "get", mock_return)
    site = SiteFactory(sitemap_url="http://localhost:8000/sitemap.xml")
    actual = list(site.get_urls())
    assert actual == []
    assert "Sitemap not fetched" in caplog.text


def test_server_error(caplog, httpserver):
    def handler(_):
        raise ValueError()

    httpserver.expect_request("/sitemap.xml").respond_with_handler(handler)
    site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
    actual = list(site.get_urls())
    assert actual == []
    assert "Sitemap not fetched" in caplog.text


def test_xml_error(caplog, httpserver):
    httpserver.expect_request("/sitemap.xml").respond_with_data(b"<urlset>")
    site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
    assert list(site.get_urls()) == []
    assert "Sitemap not parsed" in caplog.text


def test_sitemap_logging(caplog, httpserver, siteindex, compressed_sitemap):
    httpserver.expect_request("/siteindex.xml").respond_with_data(siteindex)
    httpserver.expect_request("/sitemap.xml").respond_with_data(compressed_sitemap)
    site = SiteFactory(sitemap_url=httpserver.url_for("/siteindex.xml"))
    list(site.get_urls())
    assert "Sitemap from url" in caplog.text
    assert "Sitemap fetched" in caplog.text
    assert "Sitemap is compressed" in caplog.text
    assert "Sitemap parsed" in caplog.text
    assert "Sitemap is index" in caplog.text
    assert "Sitemap is urlset" in caplog.text
    assert "Sitemap contains url" in caplog.text


def test_sitemap_file(httpserver, sitemap, urls):
    httpserver.expect_request("/sitemap.xml").respond_with_data(sitemap)
    site = SiteFactory(sitemap_file__data=sitemap)
    actual = list(site.get_urls())
    for url in urls:
        assert url in actual

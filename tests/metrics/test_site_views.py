"""
Unit tests for the site and snapshot list views, and the page HTML report view.

Covers:
  SiteListView         – lists all sites, empty state
  SiteSnapshotListView – lists snapshots for a given site; 404 for unknown site
  PageReportView       – serves the raw Lighthouse HTML; 404 when no html_report
"""

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from tests.factories import PageFactory, SiteFactory, SnapshotFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# SiteListView
# ---------------------------------------------------------------------------


class TestSiteListView:
    def test_returns_200(self, client):
        response = client.get(reverse("site-list"))
        assert response.status_code == 200

    def test_lists_all_sites(self, client):
        SiteFactory()
        SiteFactory()
        response = client.get(reverse("site-list"))
        assert response.context["sites"].count() == 2

    def test_empty_state_when_no_sites(self, client):
        response = client.get(reverse("site-list"))
        assert response.context["sites"].count() == 0
        assert response.status_code == 200

    def test_sites_ordered_by_name(self, client):
        SiteFactory(name="Zebra")
        SiteFactory(name="Alpha")
        response = client.get(reverse("site-list"))
        names = [s.name for s in response.context["sites"]]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# SiteSnapshotListView
# ---------------------------------------------------------------------------


class TestSiteSnapshotListView:
    def test_returns_200_for_existing_site(self, client):
        site = SiteFactory()
        response = client.get(reverse("site-snapshots", kwargs={"pk": site.pk}))
        assert response.status_code == 200

    def test_returns_404_for_missing_site(self, client):
        response = client.get(reverse("site-snapshots", kwargs={"pk": 999999}))
        assert response.status_code == 404

    def test_lists_snapshots_for_site(self, client):
        site = SiteFactory()
        SnapshotFactory(site=site)
        SnapshotFactory(site=site)
        # Snapshot belonging to a different site — must not appear.
        SnapshotFactory()
        response = client.get(reverse("site-snapshots", kwargs={"pk": site.pk}))
        assert response.context["snapshots"].count() == 2

    def test_context_contains_site(self, client):
        site = SiteFactory()
        response = client.get(reverse("site-snapshots", kwargs={"pk": site.pk}))
        assert response.context["site"] == site

    def test_snapshots_ordered_newest_first(self, client):
        site = SiteFactory()
        s1 = SnapshotFactory(site=site)
        s2 = SnapshotFactory(site=site)
        response = client.get(reverse("site-snapshots", kwargs={"pk": site.pk}))
        pks = [s.pk for s in response.context["snapshots"]]
        # Both snapshots present; newer one (higher pk / later created) comes first.
        assert pks.index(s2.pk) < pks.index(s1.pk)

    def test_empty_state_when_no_snapshots(self, client):
        site = SiteFactory()
        response = client.get(reverse("site-snapshots", kwargs={"pk": site.pk}))
        assert response.context["snapshots"].count() == 0
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# PageReportView
# ---------------------------------------------------------------------------


class TestPageReportView:
    def test_returns_html_report_when_present(self, client):
        page = PageFactory(audited=True)
        page.html_report.save(
            "lighthouse.html",
            ContentFile(b"<html><body>Lighthouse</body></html>"),
            save=True,
        )
        response = client.get(reverse("page-report", kwargs={"pk": page.pk}))
        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]

    def test_returns_404_when_no_html_report(self, client):
        page = PageFactory(audited=True)
        response = client.get(reverse("page-report", kwargs={"pk": page.pk}))
        assert response.status_code == 404

    def test_returns_404_for_missing_page(self, client):
        response = client.get(reverse("page-report", kwargs={"pk": 999999}))
        assert response.status_code == 404

    def test_response_contains_report_content(self, client):
        content = b"<html><body>Lighthouse report content</body></html>"
        page = PageFactory(audited=True)
        page.html_report.save("lighthouse.html", ContentFile(content), save=True)
        response = client.get(reverse("page-report", kwargs={"pk": page.pk}))
        assert b"Lighthouse report content" in response.content

"""
Shared fixtures for the metrics test suite.

``lighthouse_report``  – a minimal but structurally valid Lighthouse LHR that
    exercises both the numeric (performance) and binary (all other categories)
    code paths.  Pass it directly to Page._collect_category_metrics() /
    Page._collect_audit_metrics(), or serialise it as subprocess stdout when
    testing Page.audit() with a mocked subprocess.

``page_data``          – the *processed* format stored in Page.data after
    Page.collect_metrics() has run.  Use it to build PageFactory instances
    with realistic, queryable data when testing Snapshot.collect_metrics().

``html_page``          – a minimal HTML page as bytes, generated with Faker so
    each test run gets slightly different content.  Suitable for serving via
    pytest-httpserver.
"""

import pytest
from faker import Faker

fake = Faker()


@pytest.fixture
def html_page() -> bytes:
    """A minimal but realistic HTML page, unique per run thanks to Faker."""
    title = fake.sentence(nb_words=4)
    description = fake.sentence()
    paragraphs = "\n".join(f"    <p>{fake.paragraph()}</p>" for _ in range(3))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="description" content="{description}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body>
  <h1>{title}</h1>
{paragraphs}
</body>
</html>""".encode()


@pytest.fixture
def lighthouse_report() -> dict:
    """Minimal valid Lighthouse LHR with enough structure to exercise all
    collect_metrics code paths:

    * Three performance audits → numeric type (score × 100, ms value rounded)
    * One accessibility audit that passes  → binary type, score = 1
    * One accessibility audit that fails   → binary type, score = 0
    * One best-practices audit             → binary type
    * One SEO audit                        → binary type

    The top-level keys mirror a real LHR so the fixture can be passed
    directly to Page.collect_metrics(data) or used as mocked subprocess
    stdout in Page.audit() tests.
    """
    return {
        # Required sentinel fields checked by Page.audit()
        "runWarnings": [],
        # ------------------------------------------------------------------
        # Categories – each entry is consumed by _collect_category_metrics
        # ------------------------------------------------------------------
        "categories": {
            "performance": {
                "id": "performance",
                "title": "Performance",
                "score": 0.85,
                "auditRefs": [
                    {"id": "first-contentful-paint", "weight": 10},
                    {"id": "largest-contentful-paint", "weight": 25},
                    {"id": "total-blocking-time", "weight": 30},
                ],
            },
            "accessibility": {
                "id": "accessibility",
                "title": "Accessibility",
                "score": 0.90,
                "auditRefs": [
                    {"id": "color-contrast", "weight": 3},
                    {"id": "aria-labels", "weight": 3},
                ],
            },
            "best-practices": {
                "id": "best-practices",
                "title": "Best Practices",
                "score": 0.95,
                "auditRefs": [
                    {"id": "is-on-https", "weight": 0},
                ],
            },
            "seo": {
                "id": "seo",
                "title": "SEO",
                "score": 0.88,
                "auditRefs": [
                    {"id": "meta-description", "weight": 0},
                ],
            },
        },
        # ------------------------------------------------------------------
        # Audits – each entry is consumed by _collect_audit_metrics.
        # Every audit must appear in at least one category's auditRefs.
        # ------------------------------------------------------------------
        "audits": {
            # Numeric audits (performance category)
            "first-contentful-paint": {
                "id": "first-contentful-paint",
                "title": "First Contentful Paint",
                "score": 0.90,
                "numericValue": 1200.0,
                "numericUnit": "millisecond",
            },
            "largest-contentful-paint": {
                "id": "largest-contentful-paint",
                "title": "Largest Contentful Paint",
                "score": 0.80,
                "numericValue": 2500.0,
                "numericUnit": "millisecond",
            },
            # Millisecond value with a fractional part → should be rounded
            "total-blocking-time": {
                "id": "total-blocking-time",
                "title": "Total Blocking Time",
                "score": 0.85,
                "numericValue": 150.7,
                "numericUnit": "millisecond",
            },
            # Binary audits (non-performance)
            "color-contrast": {
                "id": "color-contrast",
                "title": "Background and foreground colors have sufficient contrast",
                "score": 1,
                "numericValue": None,
                "numericUnit": None,
            },
            # Failing binary audit
            "aria-labels": {
                "id": "aria-labels",
                "title": "ARIA input fields have accessible names",
                "score": 0,
                "numericValue": None,
                "numericUnit": None,
            },
            "is-on-https": {
                "id": "is-on-https",
                "title": "Uses HTTPS",
                "score": 1,
                "numericValue": None,
                "numericUnit": None,
            },
            "meta-description": {
                "id": "meta-description",
                "title": "Document has a meta description",
                "score": 0,
                "numericValue": None,
                "numericUnit": None,
            },
        },
    }


@pytest.fixture
def page_data() -> dict:
    """Processed page metrics in the format stored by Page.collect_metrics().

    This mirrors the output of Page._collect_category_metrics() and
    Page._collect_audit_metrics() so that Snapshot.collect_metrics() can be
    unit-tested without running Lighthouse.

    The data intentionally contains a spread of ratings so the aggregate
    queries (get_ratings, get_quantiles, get_binary_scores) return
    non-trivial results:

    * performance 85 → NEEDS_IMPROVEMENT
    * accessibility 90 → GOOD
    * best-practices 95 → GOOD
    * seo 88 → NEEDS_IMPROVEMENT
    """
    return {
        "categories": {
            "performance": {
                "id": "performance",
                "title": "Performance",
                "type": "numeric",
                "score": 85,
                "rating": 1,   # Rating.NEEDS_IMPROVEMENT
                "quantile": 17,
                "audits": ["first-contentful-paint", "total-blocking-time"],
            },
            "accessibility": {
                "id": "accessibility",
                "title": "Accessibility",
                "type": "numeric",
                "score": 90,
                "rating": 2,   # Rating.GOOD
                "quantile": 18,
                "audits": ["color-contrast"],
            },
            "best-practices": {
                "id": "best-practices",
                "title": "Best Practices",
                "type": "numeric",
                "score": 95,
                "rating": 2,   # Rating.GOOD
                "quantile": 19,
                "audits": ["is-on-https"],
            },
            "seo": {
                "id": "seo",
                "title": "SEO",
                "type": "numeric",
                "score": 88,
                "rating": 1,   # Rating.NEEDS_IMPROVEMENT
                "quantile": 17,
                "audits": ["meta-description"],
            },
        },
        "audits": {
            # Numeric (performance) audits
            "first-contentful-paint": {
                "id": "first-contentful-paint",
                "title": "First Contentful Paint",
                "category": "performance",
                "weight": 10,
                "type": "numeric",
                "score": 90,
                "value": 1200,
                "units": "millisecond",
                "quantile": 18,
                "rating": 2,   # Rating.GOOD
            },
            "total-blocking-time": {
                "id": "total-blocking-time",
                "title": "Total Blocking Time",
                "category": "performance",
                "weight": 30,
                "type": "numeric",
                "score": 85,
                "value": 150,
                "units": "millisecond",
                "quantile": 17,
                "rating": 1,   # Rating.NEEDS_IMPROVEMENT
            },
            # Binary audits
            "color-contrast": {
                "id": "color-contrast",
                "title": "Background and foreground colors have sufficient contrast",
                "category": "accessibility",
                "weight": 3,
                "type": "binary",
                "score": 1,
                "rating": 2,   # Rating.GOOD
            },
            "is-on-https": {
                "id": "is-on-https",
                "title": "Uses HTTPS",
                "category": "best-practices",
                "weight": 0,
                "type": "binary",
                "score": 1,
                "rating": 2,   # Rating.GOOD
            },
            "meta-description": {
                "id": "meta-description",
                "title": "Document has a meta description",
                "category": "seo",
                "weight": 0,
                "type": "binary",
                "score": 0,
                "rating": 0,   # Rating.POOR
            },
        },
    }

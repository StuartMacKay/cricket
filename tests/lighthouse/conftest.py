"""
Shared fixtures for the lighthouse test suite.
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
    collect_metrics code paths."""
    return {
        "runWarnings": [],
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
        "audits": {
            "first-contentful-paint": {
                "id": "first-contentful-paint",
                "title": "First Contentful Paint",
                "description": "First Contentful Paint marks the time at which the first text or image is painted.",
                "score": 0.90,
                "numericValue": 1200.0,
                "numericUnit": "millisecond",
            },
            "largest-contentful-paint": {
                "id": "largest-contentful-paint",
                "title": "Largest Contentful Paint",
                "description": "Largest Contentful Paint marks the time at which the largest text or image is painted.",
                "score": 0.80,
                "numericValue": 2500.0,
                "numericUnit": "millisecond",
            },
            "total-blocking-time": {
                "id": "total-blocking-time",
                "title": "Total Blocking Time",
                "description": "Sum of all time periods between FCP and Time to Interactive.",
                "score": 0.85,
                "numericValue": 150.7,
                "numericUnit": "millisecond",
            },
            "color-contrast": {
                "id": "color-contrast",
                "title": "Background and foreground colors have sufficient contrast",
                "description": "Low-contrast text is difficult or impossible for many users to read.",
                "score": 1,
                "numericValue": None,
                "numericUnit": None,
            },
            "aria-labels": {
                "id": "aria-labels",
                "title": "ARIA input fields have accessible names",
                "description": "Screen readers and other assistive technologies need labels to properly identify form fields.",
                "score": 0,
                "numericValue": None,
                "numericUnit": None,
            },
            "is-on-https": {
                "id": "is-on-https",
                "title": "Uses HTTPS",
                "description": "All sites should be protected with HTTPS.",
                "score": 1,
                "numericValue": None,
                "numericUnit": None,
            },
            "meta-description": {
                "id": "meta-description",
                "title": "Document has a meta description",
                "description": "Meta descriptions may be included in search results.",
                "score": 0,
                "numericValue": None,
                "numericUnit": None,
            },
        },
    }

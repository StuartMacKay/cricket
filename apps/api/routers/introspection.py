from django.http import HttpRequest
from ninja import Router

router = Router(tags=["introspection"])


@router.get("/", auth=None, summary="Hypermedia root")
def api_root(request: HttpRequest):
    """Human-readable entry point listing all available endpoints."""
    return {
        "description": "Cricket agent-native API",
        "endpoints": {
            "agent_context": request.build_absolute_uri("/api/agent-context/"),
            "schema": request.build_absolute_uri("/api/schema/"),
            "audits": request.build_absolute_uri("/api/audits/"),
            "sites": request.build_absolute_uri("/api/sites/"),
            "jobs": request.build_absolute_uri("/api/jobs/"),
            "feedback": request.build_absolute_uri("/api/feedback/"),
        },
    }


@router.get("/agent-context/", auth=None, summary="Machine-readable API context")
def agent_context(request: HttpRequest):
    """Versioned JSON document (≤ 800 tokens) describing the full API surface.

    Designed to be injected into an agent's system prompt so it can discover
    all endpoints, filter parameters, and the async contract without reading
    the OpenAPI schema.
    """
    key_name = None
    if hasattr(request, "_api_key") and request._api_key:
        key_name = request._api_key.name

    return {
        "schema_version": "1",
        "api_key_name": key_name,
        "base_url": "/api/",
        "resources": {
            "audits": {
                "list": "GET /api/audits/",
                "get": "GET /api/audits/{audit_id}/",
            },
            "sites": {
                "list": "GET /api/sites/",
                "get": "GET /api/sites/{slug}/",
            },
            "snapshots": {
                "list": "GET /api/sites/{slug}/snapshots/",
                "latest": "GET /api/sites/{slug}/snapshots/latest/",
                "create": "POST /api/sites/{slug}/snapshots/",
                "get": "GET /api/sites/{slug}/snapshots/{id}/",
            },
            "pages": {
                "list": "GET /api/sites/{slug}/snapshots/{id}/pages/",
                "get": "GET /api/sites/{slug}/snapshots/{id}/pages/{page_id}/",
            },
            "jobs": {
                "list": "GET /api/jobs/",
                "get": "GET /api/jobs/{id}/",
            },
            "feedback": {
                "create": "POST /api/feedback/",
                "list": "GET /api/feedback/ (admin key only)",
            },
        },
        "filter_params": {
            "rating": ["poor", "needs-improvement", "good"],
            "category": ["performance", "accessibility", "best-practices", "seo"],
            "status": ["pending", "running", "complete", "failed"],
        },
        "pagination": {
            "cursor_param": "cursor",
            "limit_param": "limit",
            "default_limit": 20,
            "max_limit": 100,
        },
        "async": {
            "trigger": "POST to /snapshots/ returns 202 with poll_url immediately",
            "poll": "GET /api/jobs/{id}/ until status is complete or failed; honour retry_after",
            "webhook": "Pass webhook_url in POST body to receive a completion notification",
        },
        "feedback_url": "/api/feedback/",
        "skills_url": "/docs/SKILLS.md",
    }

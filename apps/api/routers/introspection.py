"""
Introspection endpoints — no authentication required.

The agent-context endpoint assembles a compact API description for injection
into an agent's system prompt. The static sections (sites, audits, feedback,
pagination) are hand-crafted here. Per-tool sections are discovered automatically:
any installed app whose api.py module exposes an AGENT_CONTEXT dict is included.

Adding a new collector app requires no changes here — define AGENT_CONTEXT in
the app's api.py and it appears in the next request.

AGENT_CONTEXT shape expected from each tool app:

    AGENT_CONTEXT = {
        "tool": "lighthouse",           # key used in the resources dict
        "jobs": {
            "list": "GET /api/sites/{slug}/lighthouse/jobs/",
            "get":  "GET /api/sites/{slug}/lighthouse/jobs/{id}/",
        },
        "runs": {
            "list":        "GET /api/sites/{slug}/lighthouse/runs/",
            "latest":      "GET /api/sites/{slug}/lighthouse/runs/latest/",
            "get":         "GET /api/sites/{slug}/lighthouse/runs/{id}/",
            "pages":       "GET /api/sites/{slug}/lighthouse/runs/{id}/pages/",
            "page_detail": "GET /api/sites/{slug}/lighthouse/runs/{id}/pages/{page_id}/",
        },
        "filters": {          # parameters accepted by this tool's run list / latest
            "cat_performance": "bool",
            ...
        },
    }
"""

import importlib

from django.conf import settings
from django.http import HttpRequest
from ninja import Router

router = Router(tags=["introspection"])


def _discover_tool_contexts() -> dict:
    """Return per-tool context sections contributed by installed tool apps."""
    contexts = {}
    for app_label in settings.INSTALLED_APPS:
        if "." in app_label:
            continue
        try:
            module = importlib.import_module(f"{app_label}.api")
            ctx = getattr(module, "AGENT_CONTEXT", None)
            if isinstance(ctx, dict) and "tool" in ctx:
                contexts[ctx["tool"]] = {k: v for k, v in ctx.items() if k != "tool"}
        except ImportError:
            pass
    return contexts


@router.get("/", auth=None, summary="Hypermedia root")
def api_root(request: HttpRequest):
    """Human-readable entry point listing all available endpoints."""
    return {
        "description": "Cricket agent-native API",
        "endpoints": {
            "agent_context": request.build_absolute_uri("/api/agent-context/"),
            "schema": request.build_absolute_uri("/api/schema/"),
            "sites": request.build_absolute_uri("/api/sites/"),
            "audits": request.build_absolute_uri("/api/audits/"),
            "feedback": request.build_absolute_uri("/api/feedback/"),
        },
    }


@router.get("/agent-context/", auth=None, summary="Machine-readable API context")
def agent_context(request: HttpRequest):
    """Compact API description for injection into an agent's system prompt.

    The resources section is assembled from static entries (sites, audits,
    feedback) plus per-tool sections auto-discovered from installed app
    api.py modules. The schema_version is incremented when the shape changes
    in a backwards-incompatible way.
    """
    key_name = None
    if hasattr(request, "_api_key") and request._api_key:
        key_name = request._api_key.name

    resources = {
        "sites": {
            "list": "GET /api/sites/",
            "get":  "GET /api/sites/{slug}/",
        },
        "audits": {
            "list": "GET /api/audits/",
            "get":  "GET /api/audits/{audit_id}/",
        },
    }
    resources.update(_discover_tool_contexts())
    resources["feedback"] = {
        "create": "POST /api/feedback/",
        "list":   "GET /api/feedback/ (admin key only)",
    }

    return {
        "schema_version": "2",
        "api_key_name": key_name,
        "base_url": "/api/",
        "resources": resources,
        "filter_params": {
            "status":      ["pending", "running", "complete", "failed"],
            "environment": ["local", "staging", "production"],
            "rating":      ["poor", "needs-improvement", "good"],
        },
        "pagination": {
            "cursor_param":  "cursor",
            "limit_param":   "limit",
            "default_limit": 20,
            "max_limit":     100,
        },
        "notes": [
            "Runs are created by scheduled Jobs — agents do not trigger runs.",
            "The URL string is the join key across tools and across time.",
            "Filter runs by Job configuration: ?cat_performance=true, ?panel_sql=true, etc.",
        ],
        "feedback_url": "/api/feedback/",
    }

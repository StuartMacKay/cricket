from ninja import NinjaAPI

from .routers import audits, feedback, introspection, sites

from lighthouse import api as lighthouse_api
from headers   import api as headers_api
from pageweight import api as pageweight_api

api = NinjaAPI(
    title="Cricket API",
    version="2.0",
    description="Agent-native REST API for web quality audit data",
    urls_namespace="api",
)

# Introspection (no auth required)
api.add_router("/", introspection.router)

# Global resources
api.add_router("/sites/",   sites.router)
api.add_router("/audits/",  audits.router)
api.add_router("/feedback/", feedback.router)

# Per-tool routers — each tool app contributes its own router
api.add_router("/sites/{slug}/lighthouse/", lighthouse_api.router)
api.add_router("/sites/{slug}/headers/",    headers_api.router)
api.add_router("/sites/{slug}/pageweight/", pageweight_api.router)

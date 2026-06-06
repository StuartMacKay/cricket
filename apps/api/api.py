from ninja import NinjaAPI

from .routers import definitions, jobs, metrics, pages, runs, sites

api = NinjaAPI(
    title="Cricket API v2",
    version="1.0",
    description="Agent-native REST API for the audits app",
    urls_namespace="api",
)

api.add_router("/sites/", sites.router)
api.add_router("/sites/{slug}/pages/", pages.router)
api.add_router("/sites/{slug}/runs/", runs.router)
api.add_router("/sites/{slug}/metrics/", metrics.router)
api.add_router("/definitions/", definitions.router)
api.add_router("/sites/{slug}/jobs/", jobs.router)

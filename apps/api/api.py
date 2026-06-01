from ninja import NinjaAPI

from .routers import audits, feedback, introspection, jobs, pages, scans, sites

api = NinjaAPI(
    title="Cricket API",
    version="1.0",
    description="Agent-native REST API for Lighthouse audit data",
    urls_namespace="api",
)

# Introspection (no auth required)
api.add_router("/", introspection.router)
api.add_router("/audits/", audits.router)
api.add_router("/sites/", sites.router)

# Scan and page routes — nested under sites
api.add_router("/sites/{slug}/scans/", scans.router)
api.add_router("/sites/{slug}/scans/{scan_id}/pages/", pages.router)

api.add_router("/jobs/", jobs.router)
api.add_router("/feedback/", feedback.router)

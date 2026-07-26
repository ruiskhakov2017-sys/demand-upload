from fastapi import APIRouter

from app.api.routes import (
    accounts,
    audit,
    auth,
    batches,
    capabilities,
    dashboard,
    google_connections,
    health,
    jobs,
    launch_groups,
    media,
    oauth,
    operations,
    plans,
    schedules,
    settings,
    setup,
    templates,
    uploads,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(setup.router)
api_router.include_router(auth.router)
api_router.include_router(batches.router)
api_router.include_router(capabilities.router)
api_router.include_router(dashboard.router)
api_router.include_router(google_connections.router)
api_router.include_router(oauth.router)
api_router.include_router(accounts.router)
api_router.include_router(uploads.router)
api_router.include_router(media.router)
api_router.include_router(templates.router)
api_router.include_router(launch_groups.router)
api_router.include_router(plans.router)
api_router.include_router(schedules.router)
api_router.include_router(settings.router)
api_router.include_router(jobs.router)
api_router.include_router(operations.router)
api_router.include_router(audit.router)

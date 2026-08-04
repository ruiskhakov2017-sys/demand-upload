from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "demand_gen_uploader",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.jobs.tasks",
        "app.jobs.schedule_tasks",
        "app.jobs.control_center_tasks",
        "app.jobs.ai_tasks",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={
        "dispatch-due-scheduled-accounts": {
            "task": "app.jobs.dispatch_due_scheduled_accounts",
            "schedule": 15.0,
        },
        "dispatch-due-control-center-sync": {
            "task": "app.jobs.dispatch_due_control_center_sync",
            "schedule": 60.0,
        },
        "evaluate-control-center-rules": {
            "task": "app.jobs.evaluate_control_center_rules",
            "schedule": 300.0,
        },
        "cleanup-ai-retention": {
            "task": "app.jobs.cleanup_ai_retention",
            "schedule": 86400.0,
        },
    },
)

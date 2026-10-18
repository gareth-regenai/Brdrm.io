"""The worker: delivers outbox events. Later epics add file parsing and AI jobs here."""

import uuid

from celery import Celery

import boardroom.modules.identity.models  # noqa: F401  registers the identity outbox
import boardroom.modules.intake.service  # noqa: F401  registers the intake outbox and consumers
import boardroom.modules.metrics.service  # noqa: F401  registers the metrics outbox and consumers
import boardroom.modules.notify.service  # noqa: F401  registers event consumers
import boardroom.modules.setup.models  # noqa: F401  registers the setup outbox
import boardroom.modules.updates.service  # noqa: F401  registers the updates outbox and consumers
from boardroom import ops
from boardroom.config import get_settings
from boardroom.events import dispatch_pending
from boardroom.logs import configure_logging
from boardroom.modules.connectors import service as connectors
from boardroom.modules.intake import pipeline

configure_logging()
settings = get_settings()

celery_app = Celery("boardroom", broker=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "dispatch-outbox": {"task": "boardroom.dispatch", "schedule": 5.0},
        # Each connected tool is pulled once a day; the hourly check finds those due.
        "sync-connections": {"task": "boardroom.sync_connections", "schedule": 3600.0},
        "check-alerts": {"task": "boardroom.check_alerts", "schedule": 300.0},
    },
)


@celery_app.task(name="boardroom.dispatch")
def dispatch() -> int:
    return dispatch_pending()


@celery_app.task(name="boardroom.process_upload", soft_time_limit=600, time_limit=660)
def process_upload(upload_id: str, tenant_id: str, user_id: str) -> None:
    """Idempotent: an upload already past "received" is left alone."""
    pipeline.process(uuid.UUID(upload_id), uuid.UUID(tenant_id), uuid.UUID(user_id))


@celery_app.task(name="boardroom.sync_connections", soft_time_limit=1800, time_limit=1860)
def sync_connections() -> int:
    return connectors.sync_due()


@celery_app.task(name="boardroom.check_alerts")
def check_alerts() -> int:
    return len(ops.check())

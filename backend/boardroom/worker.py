"""The worker: delivers outbox events. Later epics add file parsing and AI jobs here."""

from celery import Celery

import boardroom.modules.identity.models  # noqa: F401  registers the identity outbox
import boardroom.modules.notify.service  # noqa: F401  registers event consumers
from boardroom.config import get_settings
from boardroom.events import dispatch_pending
from boardroom.logs import configure_logging

configure_logging()
settings = get_settings()

celery_app = Celery("boardroom", broker=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={"dispatch-outbox": {"task": "boardroom.dispatch", "schedule": 5.0}},
)


@celery_app.task(name="boardroom.dispatch")
def dispatch() -> int:
    return dispatch_pending()

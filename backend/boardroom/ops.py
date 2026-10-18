"""Health signals and alerts (FR-12.4): queue depth, the AI error rate and login failures.

The worker checks every few minutes. An alert is written to the log at error level, where
Render's log alerts can match it, and emailed to OPS_ALERT_EMAIL when that is set. The same
alert is not sent again within the hour. Signals are counts only: no data values.

This reads several modules' tables, so it uses plain SQL in a system session and lives
outside the modules, like the event dispatcher.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text

from boardroom.config import get_settings
from boardroom.db import system_session
from boardroom.logs import get_logger

log = get_logger(__name__)

OUTBOXES = (
    "identity.outbox",
    "intake.outbox",
    "metrics.outbox",
    "setup.outbox",
    "updates.outbox",
)
# A file still on its way through these steps is waiting on the worker.
WORKING = ("received", "understanding", "calculating", "describing")


@dataclass(frozen=True)
class Signals:
    events_waiting: int
    files_waiting: int
    ai_calls: int
    ai_errors: int
    login_failures: int


@dataclass(frozen=True)
class Alert:
    key: str
    message: str


def signals() -> Signals:
    s = get_settings()
    minutes = {"minutes": s.alert_queue_minutes}
    with system_session() as session:
        events = sum(
            session.execute(
                # Table names come from the constant above, never from input.
                text(
                    f"SELECT count(*) FROM {table} WHERE dispatched_at IS NULL "  # noqa: S608  # nosec B608
                    "AND created_at < now() - make_interval(mins => :minutes)"
                ),
                minutes,
            ).scalar_one()
            for table in OUTBOXES
        )
        files = session.execute(
            text(
                "SELECT count(*) FROM intake.uploads WHERE status = ANY(:working) "
                "AND updated_at < now() - make_interval(mins => :minutes)"
            ),
            {**minutes, "working": list(WORKING)},
        ).scalar_one()
        calls, errors = session.execute(
            text(
                "SELECT count(*), count(*) FILTER (WHERE error IS NOT NULL) "
                "FROM intake.interpretation_log "
                "WHERE source IN ('ai', 'fallback') AND created_at > now() - interval '1 hour'"
            )
        ).one()
        failures = session.execute(
            text(
                "SELECT count(*) FROM audit.audit_log WHERE action = 'auth.login_failed' "
                "AND created_at > now() - interval '15 minutes'"
            )
        ).scalar_one()
    return Signals(events, files, calls, errors, failures)


def alerts(found: Signals) -> list[Alert]:
    s = get_settings()
    out = []
    if found.events_waiting or found.files_waiting:
        out.append(
            Alert(
                "queue",
                f"The worker is behind: {found.events_waiting} events and {found.files_waiting} "
                f"files have waited over {s.alert_queue_minutes} minutes.",
            )
        )
    if found.ai_calls >= s.alert_ai_min_calls and (
        found.ai_errors / found.ai_calls >= s.alert_ai_error_rate
    ):
        out.append(
            Alert(
                "ai_errors",
                f"The AI failed on {found.ai_errors} of {found.ai_calls} files in the last hour. "
                "Those files went to manual mapping.",
            )
        )
    if found.login_failures >= s.alert_login_failures:
        out.append(
            Alert(
                "login_failures",
                f"{found.login_failures} failed sign-ins in the last 15 minutes.",
            )
        )
    return out


_last_sent: dict[str, float] = {}
QUIET_SECONDS = 3600


def check() -> list[Alert]:
    """Run by the worker. Returns the alerts that fired, whether or not they were sent."""
    from boardroom.modules.notify.mailer import Email, get_mailer

    fired = alerts(signals())
    to = get_settings().ops_alert_email
    now = time.monotonic()
    for alert in fired:
        log.error("alert", alert=alert.key, message=alert.message)
        if to and now - _last_sent.get(alert.key, -QUIET_SECONDS) >= QUIET_SECONDS:
            stamp = datetime.now(UTC).strftime("%d %b %Y, %H:%M UTC")
            get_mailer().send(
                Email(
                    to=to,
                    subject=f"BoardRoom alert: {alert.key.replace('_', ' ')}",
                    body=f"{alert.message}\n\nChecked {stamp}. See docs/runbooks.",
                )
            )
            _last_sent[alert.key] = now
    return fired


def reset() -> None:
    """Tests only: forget which alerts were sent."""
    _last_sent.clear()

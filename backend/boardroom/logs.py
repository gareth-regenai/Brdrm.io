"""Structured JSON logs carrying tenant ID and never data values (FR-12.4)."""

import logging
from contextvars import ContextVar

import structlog

tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def _add_context(
    _logger: object, _method: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    event_dict.setdefault("tenant_id", tenant_id_var.get())
    event_dict.setdefault("user_id", user_id_var.get())
    event_dict.setdefault("request_id", request_id_var.get())
    return event_dict


def configure_logging(level: int = logging.INFO) -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _add_context,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(name)
    return logger

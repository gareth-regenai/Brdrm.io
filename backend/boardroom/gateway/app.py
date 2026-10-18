"""The gateway: the only component the web app talks to (FR-10.1)."""

import contextlib
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

import boardroom.modules.intake.service  # noqa: F401  registers event consumers
import boardroom.modules.metrics.service  # noqa: F401  registers event consumers
import boardroom.modules.notify.service  # noqa: F401  registers event consumers
import boardroom.modules.setup.service  # noqa: F401  registers the setup outbox
import boardroom.modules.updates.service  # noqa: F401  registers event consumers
from boardroom.config import get_settings
from boardroom.db import get_engine
from boardroom.gateway.deps import TENANT_HEADER, bearer_user_id
from boardroom.logs import configure_logging, get_logger, request_id_var, tenant_id_var, user_id_var
from boardroom.modules.billing import service as billing
from boardroom.modules.billing.api import router as billing_router
from boardroom.modules.identity.api import router as identity_router
from boardroom.modules.identity.service import IdentityError
from boardroom.modules.intake.api import router as intake_router
from boardroom.modules.metrics.api import router as metrics_router
from boardroom.modules.setup.api import router as setup_router
from boardroom.modules.updates.api import router as updates_router

log = get_logger("gateway")

PUBLIC_PATHS = frozenset(
    {
        "/healthz",
        "/auth/signup",
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        # Stripe signs each event; the signature is checked instead of a sign-in.
        "/billing/stripe/webhook",
    }
)
# A limit passed in warn mode is reported on the response (FR-9.4).
LIMIT_HEADER = "X-Limit-Warning"
# Signed upload links carry their own short-lived token instead of a sign-in.
PUBLIC_PREFIXES = ("/storage/upload/",)


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="BoardRoom.io API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID"],
        expose_headers=[LIMIT_HEADER],
    )

    @app.middleware("http")
    async def gateway(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id_var.set(uuid.uuid4().hex)
        tenant_id_var.set(None)
        user_id_var.set(None)
        billing.start_request()
        started = time.perf_counter()
        # First token check, at the gateway. Each endpoint checks again.
        if request.method != "OPTIONS" and not is_public(request.url.path):
            try:
                user_id_var.set(str(bearer_user_id(request)))
            except HTTPException as exc:
                return JSONResponse(
                    {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
                )
        tenant_header = request.headers.get(TENANT_HEADER)
        if tenant_header:
            with contextlib.suppress(ValueError):
                tenant_id_var.set(str(uuid.UUID(tenant_header)))
        response = await call_next(request)
        warnings = billing.take_warnings()
        if warnings:
            response.headers[LIMIT_HEADER] = " ".join(warnings)
        log.info(
            "request",
            method=request.method,
            # Route template only, so ids and tokens in the path stay out of the logs.
            route=getattr(request.scope.get("route"), "path", None),
            status=response.status_code,
            ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response

    @app.exception_handler(IdentityError)
    async def identity_error(_request: Request, exc: IdentityError) -> JSONResponse:
        return JSONResponse({"detail": exc.message}, status_code=exc.code)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    app.include_router(billing_router)
    app.include_router(identity_router)
    app.include_router(intake_router)
    app.include_router(metrics_router)
    app.include_router(setup_router)
    app.include_router(updates_router)
    return app


app = create_app()

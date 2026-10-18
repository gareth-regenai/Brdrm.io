"""The gateway: the only component the web app talks to (FR-10.1)."""

import contextlib
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

import boardroom.modules.notify.service  # noqa: F401  registers event consumers
from boardroom.config import get_settings
from boardroom.db import get_engine
from boardroom.gateway.deps import TENANT_HEADER, bearer_user_id
from boardroom.logs import configure_logging, get_logger, request_id_var, tenant_id_var, user_id_var
from boardroom.modules.identity.api import router as identity_router
from boardroom.modules.identity.service import IdentityError

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
    }
)


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
    )

    @app.middleware("http")
    async def gateway(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id_var.set(uuid.uuid4().hex)
        tenant_id_var.set(None)
        user_id_var.set(None)
        started = time.perf_counter()
        # First token check, at the gateway. Each endpoint checks again.
        if request.method != "OPTIONS" and request.url.path not in PUBLIC_PATHS:
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

    app.include_router(identity_router)
    return app


app = create_app()

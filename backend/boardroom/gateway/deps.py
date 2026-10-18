"""Request context: who is calling and for which tenant (FR-2.6, FR-11.2).

Every company endpoint declares the action it performs with ``require(Action.X)``.
The role-by-endpoint matrix test reads those declarations from the routes.
"""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.db import app_session
from boardroom.events import dispatch_pending
from boardroom.logs import tenant_id_var, user_id_var
from boardroom.modules.audit import service as audit
from boardroom.modules.identity import service as identity
from boardroom.permissions import Action, Role, allowed
from boardroom.security.tokens import TokenError, verify_access_token

TENANT_HEADER = "X-Tenant-ID"


@dataclass
class UserContext:
    user_id: uuid.UUID
    session: Session


@dataclass
class TenantContext:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: Role
    departments: list[str]
    session: Session


def _unauthorised() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Sign in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this.")


def bearer_user_id(request: Request) -> uuid.UUID:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorised()
    try:
        return verify_access_token(token)
    except TokenError as exc:
        raise _unauthorised() from exc


def _after_commit(request: Request) -> None:
    """In development and tests, deliver events straight away. Elsewhere the worker does."""
    if get_settings().dispatch_inline and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        dispatch_pending()


def current_user(request: Request) -> Iterator[UserContext]:
    user_id = bearer_user_id(request)
    user_id_var.set(str(user_id))
    with app_session(user_id=user_id) as session:
        if not identity.user_exists(session, user_id):
            raise _unauthorised()
        yield UserContext(user_id=user_id, session=session)
    _after_commit(request)


def require(action: Action, audit_view: bool = False) -> Callable[..., Iterator[TenantContext]]:
    """``audit_view`` marks the endpoint that counts as an investor opening the company,
    so each visit is logged once rather than once per request the page makes."""

    def dependency(
        request: Request,
        x_tenant_id: str = Header(alias=TENANT_HEADER),
    ) -> Iterator[TenantContext]:
        user_id = bearer_user_id(request)
        try:
            tenant_id = uuid.UUID(x_tenant_id)
        except ValueError as exc:
            raise _forbidden() from exc
        user_id_var.set(str(user_id))
        tenant_id_var.set(str(tenant_id))
        with app_session(user_id=user_id, tenant_id=tenant_id) as session:
            membership = identity.active_membership(session, user_id, tenant_id)
            # Not a member and no such company give the same answer.
            if membership is None or not allowed(membership.role, action):
                raise _forbidden()
            role = membership.role
            if audit_view and role == Role.INVESTOR:
                audit.record(
                    session,
                    "investor.viewed",
                    tenant_id=tenant_id,
                    actor_user_id=user_id,
                    details={"action": action.value, "path": request.url.path},
                )
            yield TenantContext(user_id, tenant_id, role, membership.departments, session)
        _after_commit(request)

    dependency.action = action  # type: ignore[attr-defined]
    return dependency

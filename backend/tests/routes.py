"""Reads the API's routes, so the matrix and isolation tests cover every endpoint,
including new ones."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from fastapi.routing import APIRoute

from boardroom.gateway.app import PUBLIC_PATHS, app
from boardroom.gateway.deps import current_user
from boardroom.permissions import Action


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    action: Action | None
    user_level: bool

    def url(self) -> str:
        url = self.path
        for name in ("user_id", "invitation_id"):
            url = url.replace("{" + name + "}", str(uuid.uuid4()))
        return url


def _action(route: APIRoute) -> Action | None:
    for dep in route.dependant.dependencies:
        action = getattr(dep.call, "action", None)
        if action is not None:
            return action
    return None


def _api_routes(routes: list[Any]) -> Iterator[APIRoute]:
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        # Included routers are wrapped; newer FastAPI keeps the router on original_router.
        inner = getattr(route, "original_router", None) or getattr(route, "router", None)
        if inner is not None and hasattr(inner, "routes"):
            yield from _api_routes(inner.routes)


def all_routes() -> list[Route]:
    routes = []
    for route in _api_routes(app.routes):
        user_level = any(d.call is current_user for d in route.dependant.dependencies)
        for method in route.methods:
            routes.append(Route(method, route.path, _action(route), user_level))
    return sorted(routes, key=lambda r: (r.path, r.method))


def tenant_routes() -> list[Route]:
    return [r for r in all_routes() if r.action is not None]


def unguarded_routes() -> list[Route]:
    return [
        r
        for r in all_routes()
        if r.action is None and not r.user_level and r.path not in PUBLIC_PATHS
    ]


def openapi_operations() -> set[tuple[str, str]]:
    return {
        (method.upper(), path) for path, item in app.openapi()["paths"].items() for method in item
    }

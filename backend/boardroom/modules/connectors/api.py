from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from boardroom.gateway.deps import TenantContext, require
from boardroom.modules.connectors import service
from boardroom.permissions import Action

router = APIRouter()


class ToolOut(BaseModel):
    key: str
    name: str
    department: str
    sends: str
    state: str  # connected, failed, available, coming_soon, phase_2
    connected_by_name: str | None
    connected_at: datetime | None
    last_synced_at: datetime | None
    last_error: str | None


def _out(t: service.Tool) -> ToolOut:
    return ToolOut(**t.__dict__)


def _raise(exc: service.ConnectorError) -> HTTPException:
    return HTTPException(exc.code, exc.message)


@router.get("/company/connections", response_model=list[ToolOut], tags=["connectors"])
def tools(ctx: TenantContext = Depends(require(Action.MANAGE_CONNECTIONS))) -> list[ToolOut]:
    return [_out(t) for t in service.tools(ctx.session, ctx.tenant_id)]


@router.post("/company/connections/{provider}", response_model=ToolOut, tags=["connectors"])
def connect(
    provider: str, ctx: TenantContext = Depends(require(Action.MANAGE_CONNECTIONS))
) -> ToolOut:
    try:
        return _out(service.connect(ctx.session, ctx.tenant_id, ctx.user_id, provider))
    except service.ConnectorError as exc:
        raise _raise(exc) from exc


@router.post("/company/connections/{provider}/sync", response_model=ToolOut, tags=["connectors"])
def sync(
    provider: str, ctx: TenantContext = Depends(require(Action.MANAGE_CONNECTIONS))
) -> ToolOut:
    try:
        return _out(service.sync(ctx.session, ctx.tenant_id, ctx.user_id, provider))
    except service.ConnectorError as exc:
        raise _raise(exc) from exc


@router.delete("/company/connections/{provider}", status_code=204, tags=["connectors"])
def disconnect(
    provider: str, ctx: TenantContext = Depends(require(Action.MANAGE_CONNECTIONS))
) -> Response:
    try:
        service.disconnect(ctx.session, ctx.tenant_id, ctx.user_id, provider)
    except service.ConnectorError as exc:
        raise _raise(exc) from exc
    return Response(status_code=204)

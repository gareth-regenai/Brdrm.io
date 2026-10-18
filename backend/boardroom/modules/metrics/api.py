import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from boardroom.gateway.deps import TenantContext, require
from boardroom.modules.metrics import service
from boardroom.modules.metrics.registry import METRICS
from boardroom.permissions import Action

router = APIRouter()


class TileOut(BaseModel):
    id: uuid.UUID
    metric: str
    label: str
    period: str
    display: str
    status: str
    unit: str
    risk: str | None
    custom: bool
    source_line: str
    previous_period: str | None
    previous_display: str | None


class TilesOut(BaseModel):
    calculated_at: str | None
    tiles: list[TileOut]


class SettingIn(BaseModel):
    hidden: bool | None = None
    band_offset: int | None = Field(default=None, ge=-1, le=1)
    high: Decimal | None = None
    medium: Decimal | None = None
    reset_thresholds: bool = False


def _raise(exc: service.MetricsError) -> HTTPException:
    return HTTPException(exc.code, exc.message)


@router.get("/company/metrics", response_model=TilesOut, tags=["metrics"])
def tiles(
    include_hidden: bool = Query(default=False),
    ctx: TenantContext = Depends(require(Action.VIEW_FIGURES)),
) -> TilesOut:
    run, items = service.tiles(ctx.session, ctx.tenant_id, include_hidden)
    return TilesOut(
        calculated_at=run.created_at.isoformat() if run else None,
        tiles=[
            TileOut(
                id=t.figure.id,
                metric=t.figure.metric,
                label=METRICS[t.figure.metric].label,
                period=t.figure.period,
                display=t.display,
                status=t.figure.status,
                unit=METRICS[t.figure.metric].unit.value,
                risk=t.risk,
                custom=t.figure.custom,
                source_line=t.source_line,
                previous_period=t.previous.period if t.previous else None,
                previous_display=t.previous_display,
            )
            for t in items
        ],
    )


@router.get("/company/metrics/settings", response_model=list[dict[str, Any]], tags=["metrics"])
def settings(ctx: TenantContext = Depends(require(Action.VIEW_FIGURES))) -> list[dict[str, Any]]:
    return service.get_settings_view(ctx.session, ctx.tenant_id)


@router.put(
    "/company/metrics/settings/{metric}", response_model=list[dict[str, Any]], tags=["metrics"]
)
def update_setting(
    metric: str, body: SettingIn, ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))
) -> list[dict[str, Any]]:
    try:
        service.update_setting(
            ctx.session,
            ctx.tenant_id,
            ctx.user_id,
            metric,
            body.hidden,
            body.band_offset,
            body.high,
            body.medium,
            body.reset_thresholds,
        )
    except service.MetricsError as exc:
        raise _raise(exc) from exc
    return service.get_settings_view(ctx.session, ctx.tenant_id)


@router.get("/company/metrics/{figure_id}", response_model=dict[str, Any], tags=["metrics"])
def trace(
    figure_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.VIEW_FIGURES))
) -> dict[str, Any]:
    """The click view (FR-5.4)."""
    try:
        return service.trace(ctx.session, ctx.tenant_id, figure_id)
    except service.MetricsError as exc:
        raise _raise(exc) from exc

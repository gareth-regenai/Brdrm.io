"""The tools a company can connect. Each pulls files: whatever it sends then takes the same
path as an export the company uploads, so no figure depends on which tool sent it.

A real connector needs that tool's developer app (its client id and secret) and signs the
company in once with read-only access. Until a tool's connector is built it shows as
"Coming soon", and an export from it works as before.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from boardroom.config import Settings

DEMO = Path(__file__).parent / "demo"


class PullFailed(Exception):
    """A tool could not be reached or refused. The message is shown to the company."""


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    department: str
    # What it sends, in a phrase: "Profit and loss and bank balance".
    sends: str
    # Built and allowed here. A tool that is not is "Coming soon".
    ready: Callable[[Settings], bool] = lambda _s: False
    # Phase 2 tools wait for their feature flag (FR-1.3).
    flag: str | None = None
    pull: Callable[[], list[tuple[str, bytes]]] = field(default=lambda: [])


def _demo() -> list[tuple[str, bytes]]:
    return [
        ("Demo company: profit and loss.csv", (DEMO / "profit_and_loss.csv").read_bytes()),
        ("Demo company: deals.csv", (DEMO / "deals.csv").read_bytes()),
    ]


PROVIDERS: dict[str, Provider] = {
    p.key: p
    for p in (
        Provider(
            "demo",
            "Demo company",
            "finance",
            "Sample books and deals, to try BoardRoom",
            ready=lambda s: s.connectors_demo,
            pull=_demo,
        ),
        Provider("xero", "Xero", "finance", "Profit and loss and bank balance"),
        Provider("quickbooks", "QuickBooks", "finance", "Profit and loss and bank balance"),
        Provider("hubspot", "HubSpot", "sales", "Deals and their stages"),
        Provider("pipedrive", "Pipedrive", "sales", "Deals and their stages"),
        Provider("jira", "Jira", "delivery", "Epics and story points", flag="product_delivery"),
        Provider("monday", "monday.com", "delivery", "Items against plan", flag="product_delivery"),
        Provider("hibob", "HiBob", "people", "Headcount. Pay is never kept", flag="people"),
    )
}

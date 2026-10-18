"""FRD chapter 7: the investor's portfolio overview.

Each company's card shows only what it has shared, on the common warning lines, in its
own currency and precision. Companies are built from the QuickBooks layout with different
bank balances, so each has a known runway.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tests.conftest import upload_file

BURN = Decimal("69800")  # the file's average net burn, so runway = cash / burn


def books(cash_at_end: Decimal) -> bytes:
    """quickbooks_monthly.csv with the bank balance moved to end at ``cash_at_end``."""
    months = ["Apr-26", "May-26", "Jun-26", "Jul-26", "Aug-26", "Sep-26"]
    income = [58000, 60100, 62200, 64300, 66400, 68500]
    cogs = [9500, 9760, 10020, 10280, 10540, 10800]
    expenses = [118000, 119900, 121800, 123700, 125600, 127500]
    lines = ["Month,Income,Cost of goods sold,Expenses,Net income,Bank balance,Currency"]
    for i, month in enumerate(months):
        net = income[i] - cogs[i] - expenses[i]
        balance = cash_at_end + (5 - i) * BURN
        lines.append(
            f'{month},"£{income[i]:,}.00","£{cogs[i]:,}.00","£{expenses[i]:,}.00",'
            f'"(£{-net:,}.00)","£{balance:,.2f}",GBP'
        )
    return ("\n".join(lines) + "\n").encode()


@pytest.fixture
def backed(client, make_company, invite, recorded_ai):
    """An investor, and a way to add a company they back with a shared update."""
    investor = None

    def add(name, cash=None, share=True):
        nonlocal investor
        company = make_company(name)
        h = company.owner.auth(company.tenant_id)
        data = books(Decimal(cash)) if cash is not None else None
        upload_file(client, company, "quickbooks_monthly.csv", data=data)
        [update] = client.get("/company/updates", headers=h).json()
        if share:
            client.post(f"/company/updates/{update['id']}/approve", headers=h)
        if investor is None:
            investor = invite(company, "investor")
        else:
            invite(company, "investor", existing=investor)
        return company, update

    def view():
        r = client.get("/portfolio/overview", headers=investor.auth())
        assert r.status_code == 200, r.text
        return r.json()

    return add, view


def _measures(card):
    return {m["key"]: m for m in card["measures"]}


# FR-7.1, FR-7.2


def test_an_investor_in_three_companies_sees_three_cards(backed, make_company, recorded_ai):
    add, view = backed
    for name in ("Alder Labs", "Kestrel Field", "Northpath"):
        add(name)
    make_company("Not Theirs")
    cards = view()
    assert sorted(c["name"] for c in cards) == ["Alder Labs", "Kestrel Field", "Northpath"]
    m = _measures(cards[0])
    assert [x["label"] for x in cards[0]["measures"]] == [
        "Cash",
        "Runway",
        "Net burn",
        "Revenue v plan",
        "Pipeline coverage",
        "Delivery v plan",
        "Headcount v plan",
        "Last update",
    ]
    assert m["cash_balance"]["display"] == "£1,194.5k"  # the company's own precision
    assert m["runway"]["display"] == "17.1 months" and m["runway"]["risk"] == "low"


def test_two_companies_with_the_same_runway_get_the_same_level(backed):
    add, view = backed
    add("Alder Labs", cash="698000")
    add("Kestrel Field", cash="698000")
    levels = {_measures(c)["runway"]["risk"] for c in view()}
    assert levels == {"medium"}  # 10.0 months, between the common lines of 6 and 12


def test_the_overview_uses_the_common_lines_not_the_companys_own(backed, client):
    add, view = backed
    company, _ = add("Kestrel Field")
    h = company.owner.auth(company.tenant_id)
    # The company makes its own runway line much stricter. Its own tiles change...
    client.put("/company/metrics/settings/runway", headers=h, json={"high": "20", "medium": "30"})
    tiles = client.get("/company/metrics", headers=h).json()["tiles"]
    assert next(t for t in tiles if t["metric"] == "runway")["risk"] == "high"
    # ...the investor overview does not (FR-5.7).
    assert _measures(view()[0])["runway"]["risk"] == "low"


# FR-7.3: highest risk first


def test_cards_sort_by_high_then_medium_then_shortest_runway(backed):
    add, view = backed
    add("Low and long", cash="1194500")  # 17.1 months
    add("High", cash="279200")  # 4.0 months
    add("Low and shorter", cash="1047000")  # 15.0 months
    add("Medium", cash="698000")  # 10.0 months
    cards = view()
    assert [c["name"] for c in cards] == ["High", "Medium", "Low and shorter", "Low and long"]
    assert [c["risk"] for c in cards] == ["high", "medium", "low", "low"]


# FR-7.4, FR-7.6: one click to the latest update, and days since it


def test_the_card_leads_to_the_latest_update_and_counts_days(backed, owner_conn):
    add, view = backed
    company, update = add("Kestrel Field")
    [card] = view()
    assert card["latest_update_id"] == update["id"]
    last = _measures(card)["last_update"]
    assert last["display"] == "Today" and last["risk"] == "low"
    owner_conn.execute(
        "UPDATE updates.updates SET approved_at = %s",
        (datetime.now(UTC) - timedelta(days=41),),
    )
    last = _measures(view()[0])["last_update"]
    assert last["display"] == "41 days" and last["risk"] == "high"


# FR-7.5: phase 2 measures


def test_delivery_and_headcount_say_coming_in_phase_2(backed, monkeypatch):
    from boardroom.config import get_settings

    add, view = backed
    add("Kestrel Field")
    m = _measures(view()[0])
    assert m["delivery_vs_plan"]["display"] == "Coming in phase 2"
    assert m["headcount"]["display"] == "Coming in phase 2"
    monkeypatch.setattr(get_settings().flags, "people", True)
    assert _measures(view()[0])["headcount"]["display"] == "Not shared yet"


# FR-7.7: company roles cannot reach it


def test_company_users_are_refused(client, make_company, invite):
    company = make_company()
    ceo = invite(company, "ceo")
    for account in (company.owner, ceo):
        assert client.get("/portfolio/overview", headers=account.auth()).status_code == 403


# FR-7.8: no totals, and only what was shared


def test_money_is_never_totalled(backed):
    add, view = backed
    add("Alder Labs")
    add("Kestrel Field")
    cards = view()
    assert isinstance(cards, list)  # a list of cards, with nothing summed beside it
    for card in cards:
        assert set(card) == {"tenant_id", "name", "risk", "measures", "latest_update_id"}


def test_only_shared_figures_reach_the_overview(backed, client):
    add, view = backed
    company, update = add("Kestrel Field", share=False)
    m = _measures(view()[0])
    assert m["runway"]["display"] == "Not shared yet" and m["runway"]["available"] is False
    assert m["last_update"]["display"] == "None yet"
    assert view()[0]["risk"] is None

    h = company.owner.auth(company.tenant_id)
    client.post(f"/company/updates/{update['id']}/approve", headers=h)
    runway = next(f for f in update["figures"] if f["metric"] == "runway")
    client.put(
        f"/company/updates/{update['id']}/figures/{runway['figure_id']}",
        headers=h,
        json={"value": "4"},
    )
    m = _measures(view()[0])
    # The overview shows the figure as the company shared it, on the common lines.
    assert m["runway"]["display"] == "4.0 months" and m["runway"]["risk"] == "high"


def test_each_view_is_in_each_companys_audit_log(backed, owner_conn):
    add, view = backed
    add("Alder Labs")
    add("Kestrel Field")
    view()
    rows = owner_conn.execute(
        "SELECT count(DISTINCT tenant_id) FROM audit.audit_log "
        "WHERE action = 'investor.viewed' AND details->>'page' = 'portfolio overview'"
    ).fetchone()
    assert rows[0] == 2

"""FRD chapter 5 and FR-1.1, 1.2, 13.3: the figures engine.

The golden datasets below were calculated by hand before the code ran; the working is in
the comments. A formula change that moves any of them fails here.
"""

import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from boardroom.modules.intake.service import DatasetView, ManualFigureView
from boardroom.modules.metrics import compute, selection
from boardroom.modules.metrics.display import band_for, format_money, format_value
from tests.conftest import upload_file

D = Decimal


def dataset(
    kind: str, rows: list[dict], as_of: date | None = None, name: str = "file.csv"
) -> DatasetView:
    fields = sorted({k for r in rows for k in r})
    return DatasetView(
        uuid.uuid4(),
        kind,
        1,
        uuid.uuid4(),
        name,
        tuple(fields),
        as_of,
        datetime.now(UTC),
        tuple(enumerate(rows)),
    )


def ctx(*datasets: DatasetView, manual: list[ManualFigureView] | None = None) -> compute.Context:
    sels = {}
    for ds in datasets:
        for key, rs in selection.ROW_SETS.items():
            if rs.kind == ds.kind:
                sels[(str(ds.id), key)] = selection.standard(key, ds)
    return compute.Context(list(datasets), sels, manual or [], "GBP", today=date(2026, 10, 18))


def manual(metric: str, period: str, value: str, kind: str = "actual") -> ManualFigureView:
    return ManualFigureView(
        uuid.uuid4(),
        metric,
        period,
        D(value),
        kind,
        "Priya Shah",
        datetime(2026, 10, 1, tzinfo=UTC),
    )


def find(figures, metric, period):
    return next(f for f in figures if f.metric == metric and f.period == period)


FINANCE = [
    {
        "period": "2026-06",
        "revenue": "50000",
        "cost_of_sales": "10000",
        "operating_expenses": "120000",
        "cash_balance": "1000000",
    },
    {
        "period": "2026-07",
        "revenue": "55000",
        "cost_of_sales": "11000",
        "operating_expenses": "121000",
        "cash_balance": "923000",
    },
    {
        "period": "2026-08",
        "revenue": "60500",
        "cost_of_sales": "12100",
        "operating_expenses": "122000",
        "cash_balance": "849600",
    },
    {
        "period": "2026-09",
        "revenue": "60000",
        "cost_of_sales": "12000",
        "operating_expenses": "123500",
        "cash_balance": "774100",
    },
]


# FR-13.3: golden finance


def test_golden_finance():
    figures = compute.compute_all(ctx(dataset("finance", FINANCE)))
    # Net burn = cost of sales + operating expenses - revenue.
    assert [
        find(figures, "net_burn", p).value for p in ("2026-06", "2026-07", "2026-08", "2026-09")
    ] == [D(80000), D(77000), D(73600), D(75500)]
    # Runway in Sep = 774,100 / ((77,000 + 73,600 + 75,500) / 3) = 2,322,300 / 226,100.
    assert find(figures, "runway", "2026-09").value == D(774100) / (D(226100) / 3)
    assert str(find(figures, "runway", "2026-09").value)[:7] == "10.2711"
    # Runway in Aug = 849,600 / ((80,000 + 77,000 + 73,600) / 3).
    assert str(find(figures, "runway", "2026-08").value)[:7] == "11.0529"
    # Runway needs three months of burn: not shown for Jun or Jul.
    assert not [f for f in figures if f.metric == "runway" and f.period in ("2026-06", "2026-07")]
    # Gross margin in Sep = (60,000 - 12,000) / 60,000.
    assert find(figures, "gross_margin", "2026-09").value == D("0.8")
    # Growth in Aug = (60,500 - 55,000) / 55,000; in Sep = (60,000 - 60,500) / 60,500.
    assert find(figures, "revenue_growth", "2026-08").value == D("0.1")
    assert str(find(figures, "revenue_growth", "2026-09").value)[:8] == "-0.00826"
    assert find(figures, "cash_balance", "2026-09").value == D(774100)
    # No target: the plan tile says so instead of failing (FR-4.11).
    assert find(figures, "revenue_vs_plan", "2026-09").status == "no_plan"
    # Annual revenue = (50,000 + 55,000 + 60,500 + 60,000) x 12 / 4 = 676,500: the £k band.
    assert compute.annual_revenue(figures) == D(676500)
    assert band_for(compute.annual_revenue(figures)) == 1


def test_golden_finance_display():
    figures = compute.compute_all(ctx(dataset("finance", FINANCE)))
    band = band_for(compute.annual_revenue(figures))
    show = lambda m: format_value(find(figures, m, "2026-09").value, m, band)  # noqa: E731
    assert show("revenue") == "£60.0k"
    assert show("cash_balance") == "£774.1k"
    assert show("net_burn") == "£75.5k"
    assert show("runway") == "10.3 months"
    assert show("gross_margin") == "80.0%"
    assert show("revenue_growth") == "-0.8%"


def test_golden_plan_variance():
    figures = compute.compute_all(
        ctx(dataset("finance", FINANCE), manual=[manual("revenue", "2026-09", "64000", "target")])
    )
    f = find(figures, "revenue_vs_plan", "2026-09")
    # 60,000 - 64,000; 60,000 / 64,000 = 0.9375 of plan.
    assert f.value == D(-4000)
    assert D(f.extra["percent_of_plan"]) == D("0.9375")
    assert f.lineage.manual[0]["entered_by"] == "Priya Shah"


def test_golden_cash_movement_method_is_flagged():
    # Only bank balances: the standard burn formula cannot work, so burn is the fall in cash.
    cash_only = [{"period": r["period"], "cash_balance": r["cash_balance"]} for r in FINANCE]
    figures = compute.compute_all(ctx(dataset("finance", cash_only)))
    jul = find(figures, "net_burn", "2026-07")
    assert jul.value == D(77000) and jul.method == "cash_movement" and jul.custom
    # 1,000,000 - 923,000; 923,000 - 849,600; 849,600 - 774,100.
    assert [find(figures, "net_burn", p).value for p in ("2026-07", "2026-08", "2026-09")] == [
        D(77000),
        D(73400),
        D(75500),
    ]
    runway = find(figures, "runway", "2026-09")
    assert runway.custom and runway.value == D(774100) / ((D(77000) + D(73400) + D(75500)) / 3)


def test_golden_cash_generative():
    profitable = [{**r, "revenue": "200000"} for r in FINANCE]
    f = find(compute.compute_all(ctx(dataset("finance", profitable))), "runway", "2026-09")
    assert f.status == "cash_generative" and f.value is None


SALES = [
    {
        "deal_id": "A",
        "status": "open",
        "amount": "10000",
        "probability": "0.5",
        "expected_close_date": "2026-09-20",
        "last_activity_date": "2026-09-25",
        "currency": "GBP",
    },
    {
        "deal_id": "B",
        "status": "open",
        "amount": "20000",
        "probability": "0.25",
        "expected_close_date": "2026-10-15",
        "last_activity_date": "2026-08-01",
        "currency": "GBP",
    },
    {
        "deal_id": "C",
        "status": "open",
        "amount": "5000",
        "probability": "0.8",
        "expected_close_date": "2026-09-28",
        "last_activity_date": "2026-07-10",
        "currency": "GBP",
    },
    {
        "deal_id": "D",
        "status": "open",
        "amount": "8000",
        "probability": "0.5",
        "expected_close_date": "2026-09-10",
        "last_activity_date": "2026-09-01",
        "currency": "USD",
    },
    {
        "deal_id": "E",
        "status": "won",
        "amount": "12000",
        "closed_date": "2026-09-05",
        "currency": "GBP",
    },
    {
        "deal_id": "F",
        "status": "won",
        "amount": "6000",
        "closed_date": "2026-09-18",
        "currency": "GBP",
    },
    {
        "deal_id": "G",
        "status": "won",
        "amount": "9000",
        "closed_date": "2026-08-11",
        "currency": "GBP",
    },
    {
        "deal_id": "H",
        "status": "lost",
        "amount": "7000",
        "closed_date": "2026-09-12",
        "currency": "GBP",
    },
    {
        "deal_id": "I",
        "status": "lost",
        "amount": "4000",
        "closed_date": "2026-08-20",
        "currency": "GBP",
    },
]


def test_golden_sales():
    sales = dataset("sales", SALES, as_of=date(2026, 9, 30))
    figures = compute.compute_all(
        ctx(sales, manual=[manual("closed_won", "2026-09", "40000", "target")])
    )
    pipe = find(figures, "pipeline", "2026-09")
    # Open GBP deals A + B + C. D is in dollars and left out until conversion (phase 2).
    assert pipe.value == D(35000) and pipe.extra == {"other_currency_rows_left_out": 1}
    # 10,000 x 0.5 + 20,000 x 0.25 + 5,000 x 0.8.
    assert find(figures, "weighted_pipeline", "2026-09").value == D(14000)
    # Last activity before 31 Aug (30 days before 30 Sep): B and C. 2 of 3 open deals.
    stalled = find(figures, "stalled_deals", "2026-09")
    assert stalled.value == 2 and stalled.risk_measure == D(2) / D(3)
    # September: won E and F, lost H. August: won G, lost I.
    assert find(figures, "win_rate", "2026-09").value == D(2) / D(3)
    assert find(figures, "win_rate", "2026-08").value == D("0.5")
    assert find(figures, "avg_deal_size", "2026-09").value == D(9000)
    # Due in September: A + C = 15,000. Still needed: 40,000 - 18,000 won = 22,000.
    coverage = find(figures, "coverage", "2026-09")
    assert coverage.value == D(15000) / D(22000)
    assert format_value(coverage.value, "coverage", 1) == "0.7x"


def test_coverage_says_when_the_target_is_met():
    sales = dataset("sales", SALES, as_of=date(2026, 9, 30))
    figures = compute.compute_all(
        ctx(sales, manual=[manual("closed_won", "2026-09", "15000", "target")])
    )
    assert find(figures, "coverage", "2026-09").status == "target_met"


def test_weighted_pipeline_needs_every_probability():
    rows = [
        {k: v for k, v in r.items() if k != "probability"} if r["deal_id"] == "A" else r
        for r in SALES
    ]
    f = find(
        compute.compute_all(ctx(dataset("sales", rows, as_of=date(2026, 9, 30)))),
        "weighted_pipeline",
        "2026-09",
    )
    assert f.status == "not_provided" and f.extra == {"open_deals_without_amount_or_probability": 1}


def test_blank_cells_are_never_zero():
    rows = [dict(FINANCE[3]), {**FINANCE[2], "revenue": ""}]
    figures = compute.compute_all(ctx(dataset("finance", rows)))
    assert all(f.status == "not_provided" for f in figures if f.metric == "revenue_growth")


# FR-5.6: display precision


@pytest.mark.parametrize(
    "value, band, expected",
    [
        ("4210", 0, "£4,210"),
        ("4210.5", 0, "£4,211"),
        ("78100", 1, "£78.1k"),
        ("78150", 1, "£78.2k"),
        ("1378000", 2, "£1.378m"),
        ("950500", 2, "£950.5k"),
        ("13780000", 3, "£13.78m"),
        ("950500", 3, "£951k"),
        ("137800000", 4, "£137.8m"),
        ("-75500", 1, "-£75.5k"),
    ],
)
def test_money_precision_by_band(value, band, expected):
    assert format_money(D(value), band) == expected


@pytest.mark.parametrize(
    "revenue, band",
    [
        (None, 0),
        ("0", 0),
        ("99999", 0),
        ("100000", 1),
        ("999999", 1),
        ("1000000", 2),
        ("10000000", 3),
        ("100000000", 4),
    ],
)
def test_bands_follow_annual_revenue(revenue, band):
    assert band_for(D(revenue) if revenue else None) == band


def test_months_and_percentages_show_one_decimal():
    assert format_value(D("17.55"), "runway", 3) == "17.6 months"
    assert format_value(D("0.41649"), "gross_margin", 3) == "41.6%"
    assert format_value(D("0.41650"), "gross_margin", 3) == "41.7%"


# FR-5.2: the closed filter set


def _sel(row_set, filters, reason="r"):
    return {"row_set": row_set, "filters": filters, "reason": reason}


def test_selections_outside_the_closed_set_are_rejected():
    sales = dataset("sales", SALES)
    good = {
        "selections": [
            _sel("open_deals", [{"op": "in", "field": "status", "values": ["open"]}]),
            _sel("won_deals", [{"op": "in", "field": "status", "values": ["won"]}]),
            _sel("lost_deals", [{"op": "not_in", "field": "status", "values": ["open", "won"]}]),
        ]
    }
    assert [s.source for s in selection.validate(good, sales)] == ["ai", "ai", "ai"]
    bad_cases = [
        {"selections": good["selections"][:2]},  # a row set missing
        {**good, "value": 35000},  # a number where none belongs
        {
            "selections": [
                _sel("open_deals", [{"op": "where", "field": "status", "values": ["open"]}]),
                *good["selections"][1:],
            ]
        },
        {
            "selections": [
                _sel("open_deals", [{"op": "in", "field": "salary", "values": ["x"]}]),
                *good["selections"][1:],
            ]
        },
        {
            "selections": [
                _sel("open_deals", [{"op": "in", "field": "status", "values": ["pending"]}]),
                *good["selections"][1:],
            ]
        },
        {"selections": [{**good["selections"][0], "amount": "1"}, *good["selections"][1:]]},
        {"selections": [_sel("finance_actuals", []), *good["selections"][1:]]},
    ]
    for bad in bad_cases:
        with pytest.raises(selection.SelectionError):
            selection.validate(bad, sales)


def test_a_selection_changes_which_rows_feed_a_figure_never_the_formula():
    sales = dataset("sales", SALES, as_of=date(2026, 9, 30))
    c = ctx(sales)
    c.selections[(str(sales.id), "open_deals")] = selection.Selection(
        "open_deals", (selection.Filter("in", "deal_id", ("A",)),), "ai"
    )
    assert find(compute.compute_all(c), "pipeline", "2026-09").value == D(10000)


# FR-1.1: no figure from an AI response


def test_the_formulas_never_read_an_ai_response():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(compute))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "boardroom.modules.intake.skill1" not in imported
    assert not any("interpret" in getattr(n, "attr", "") for n in ast.walk(tree))


class Skill2:
    model = "recorded"

    def __init__(self, answer):
        self.answer = answer
        self.payloads = []

    def interpret(self, payload):
        self.payloads.append(payload)
        return self.answer


@pytest.fixture
def skill2():
    holder = {}

    def install(answer):
        client = Skill2(answer)
        selection.set_client(client)
        holder["c"] = client
        return client

    yield install
    selection.set_client(None)


def _tiles(client, company):
    return {
        t["metric"]: t
        for t in client.get(
            "/company/metrics", headers=company.owner.auth(company.tenant_id)
        ).json()["tiles"]
    }


def test_ai_selection_changes_rows_not_values(
    client, make_company, recorded_ai, skill2, owner_conn
):
    company = make_company()
    # Skill 2 answers that only Pipedrive's "won" deals count as won, and adds a figure of its own.
    ai = skill2(
        {
            "selections": [
                _sel("open_deals", [{"op": "in", "field": "status", "values": ["open"]}]),
                _sel("won_deals", [{"op": "in", "field": "status", "values": ["won"]}]),
                _sel("lost_deals", [{"op": "in", "field": "status", "values": ["lost"]}]),
            ]
        }
    )
    upload_file(client, company, "pipedrive_deals.xlsx")
    assert ai.payloads, "skill 2 was asked"
    payload = ai.payloads[0]["user"]
    # Aggregates only: no customer names, deal titles or amounts, just category values.
    for private in ("Deal 001", "Prospect 0 Ltd", "Priya Shah", "3500"):
        assert private not in payload, private
    assert '"values": ["lost", "open", "won"]' in payload
    stored = owner_conn.execute("SELECT source FROM metrics.selections").fetchall()
    assert {s for (s,) in stored} == {"ai"}
    values = {
        r[0]: r[1]
        for r in owner_conn.execute(
            "SELECT metric, value FROM metrics.figures WHERE status = 'ok'"
        ).fetchall()
    }
    # Every figure value is code's arithmetic on the rows: pipeline = sum of open deal values.
    open_values = [
        3500 + (i * 2210) % 38000
        for i in range(30)
        if ["open", "open", "won", "lost", "open", "won"][i % 6] == "open"
    ]
    assert D(values["pipeline"]) == D(sum(open_values))


def test_bad_ai_selection_falls_back_to_the_standard(
    client, make_company, recorded_ai, skill2, owner_conn
):
    company = make_company()
    skill2({"selections": [], "pipeline": 1_000_000})
    upload_file(client, company, "hubspot_deals.csv")
    rows = owner_conn.execute("SELECT source, reason FROM metrics.selections").fetchall()
    assert {s for s, _ in rows} == {"standard"}
    assert all(r.startswith("SelectionError") for _, r in rows)
    assert "1000000" not in json.dumps(_tiles(client, company))


# FR-1.2, FR-5.4: lineage and the click view


def test_every_figure_traces_to_rows_or_a_person(client, make_company, recorded_ai, owner_conn):
    company = make_company()
    for name in ("xero_pnl.csv", "quickbooks_monthly.csv", "hubspot_deals.csv"):
        assert upload_file(client, company, name)["status"] == "ready"
    client.post(
        "/company/figures",
        headers=company.owner.auth(company.tenant_id),
        json={"metric": "revenue", "period": "2026-09", "value": "70000", "kind": "target"},
    )
    figures = owner_conn.execute(
        "SELECT metric, lineage, formula_version FROM metrics.figures WHERE status = 'ok' "
        "AND run_id = (SELECT id FROM metrics.runs ORDER BY created_at DESC LIMIT 1)"
    ).fetchall()
    assert len(figures) > 20
    for metric, lineage, version in figures:
        assert version, metric
        has_rows = any(d["rows"] and d["version"] for d in lineage["datasets"])
        has_person = any(m["entered_by"] and m["entered_at"] for m in lineage["manual"])
        assert has_rows or has_person, metric


def test_click_view_shows_value_source_moves_and_risk(client, make_company, recorded_ai):
    company = make_company()
    upload_file(client, company, "quickbooks_monthly.csv")
    h = company.owner.auth(company.tenant_id)
    tiles = _tiles(client, company)
    cash = client.get(f"/company/metrics/{tiles['cash_balance']['id']}", headers=h).json()
    assert cash["value"] == "1194500.00"  # the exact value, unrounded
    assert cash["sources"][0]["filename"] == "quickbooks_monthly.csv"
    assert cash["sources"][0]["rows"][0]["cash_balance"] == "1194500.00"
    assert cash["moves"] == ["Runway"]
    runway = client.get(f"/company/metrics/{tiles['runway']['id']}", headers=h).json()
    assert runway["risk"] in ("high", "medium", "low") and runway["thresholds"]["high"] == "6"
    assert "average net burn" in runway["formula"] and runway["formula_version"] == "1"


def test_click_view_for_a_hand_entered_figure(client, make_company):
    company = make_company()
    h = company.owner.auth(company.tenant_id)
    client.post(
        "/company/figures",
        headers=h,
        json={"metric": "cash_balance", "period": "2026-09", "value": "500000", "kind": "actual"},
    )
    tile = _tiles(client, company)["cash_balance"]
    assert tile["source_line"].startswith("Entered by Owner of")
    trace = client.get(f"/company/metrics/{tile['id']}", headers=h).json()
    assert trace["sources"] == [] and trace["entered_by_hand"][0]["entered_by"].startswith(
        "Owner of"
    )


def test_custom_method_is_flagged_everywhere(client, make_company, owner_conn):
    company = make_company()
    h = company.owner.auth(company.tenant_id)
    for period, value in (
        ("2026-06", "1000000"),
        ("2026-07", "923000"),
        ("2026-08", "849600"),
        ("2026-09", "774100"),
    ):
        client.post(
            "/company/figures",
            headers=h,
            json={"metric": "cash_balance", "period": period, "value": value, "kind": "actual"},
        )
    tile = _tiles(client, company)["net_burn"]
    assert tile["custom"] and tile["source_line"].endswith("Custom method")
    trace = client.get(f"/company/metrics/{tile['id']}", headers=h).json()
    assert trace["method"] == "cash_movement" and "cannot work" in trace["method_note"]
    # The database refuses a custom method without its flag (FR-5.3).
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation):
        owner_conn.execute(
            "UPDATE metrics.figures SET custom = false WHERE method = 'cash_movement'"
        )


# Tiles, statuses and the upload timeline


def test_uploads_move_to_ready_once_figures_exist(client, make_company, recorded_ai, owner_conn):
    company = make_company()
    upload = upload_file(client, company, "xero_pnl.csv")
    assert upload["status"] == "ready"
    tiles = _tiles(client, company)
    assert tiles["revenue"]["display"] == "£72.9k" and tiles["revenue"]["period"] == "2026-09"
    assert tiles["revenue"]["previous_display"] == "£70.4k"
    assert tiles["cash_balance"]["display"] == "Not provided"  # a P&L has no bank balance
    assert tiles["revenue_vs_plan"]["display"] == "No plan set"


def test_a_target_entered_by_hand_fills_the_plan_tile(client, make_company, recorded_ai):
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    client.post(
        "/company/figures",
        headers=company.owner.auth(company.tenant_id),
        json={"metric": "revenue", "period": "2026-09", "value": "80000", "kind": "target"},
    )
    tile = _tiles(client, company)["revenue_vs_plan"]
    # 72,880 - 80,000.
    assert tile["display"] == "-£7.1k" and tile["risk"] == "medium"


# FR-5.6, FR-5.7: the company's own view


def test_company_can_move_a_measure_up_a_band(client, make_company, recorded_ai):
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    h = company.owner.auth(company.tenant_id)
    r = client.put("/company/metrics/settings/revenue", headers=h, json={"band_offset": -1})
    assert r.status_code == 200
    assert _tiles(client, company)["revenue"]["display"] == "£72,880"


def test_company_thresholds_change_its_tiles_not_the_overview(
    client, make_company, recorded_ai, owner_conn
):
    company = make_company()
    upload_file(client, company, "quickbooks_monthly.csv")
    h = company.owner.auth(company.tenant_id)
    before = _tiles(client, company)["runway"]["risk"]
    common = owner_conn.execute(
        "SELECT risk_common FROM metrics.figures WHERE id = %s",
        (_tiles(client, company)["runway"]["id"],),
    ).fetchone()[0]
    # Runway is about 17 months. Raise the company's lines so it reads as high risk.
    r = client.put(
        "/company/metrics/settings/runway", headers=h, json={"high": "24", "medium": "36"}
    )
    assert r.status_code == 200, r.text
    tile = _tiles(client, company)["runway"]
    assert (before, tile["risk"]) == ("low", "high")
    after_common = owner_conn.execute(
        "SELECT risk_common FROM metrics.figures WHERE id = %s", (tile["id"],)
    ).fetchone()[0]
    assert common == after_common == "low"


def test_company_can_hide_a_measure(client, make_company, recorded_ai):
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    client.put(
        "/company/metrics/settings/revenue_growth",
        headers=company.owner.auth(company.tenant_id),
        json={"hidden": True},
    )
    assert "revenue_growth" not in _tiles(client, company)


def test_warning_lines_must_make_sense(client, make_company):
    company = make_company()
    h = company.owner.auth(company.tenant_id)
    assert (
        client.put(
            "/company/metrics/settings/runway", headers=h, json={"high": "12", "medium": "6"}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/company/metrics/settings/revenue", headers=h, json={"high": "1", "medium": "2"}
        ).status_code
        == 422
    )
    assert client.put("/company/metrics/settings/nope", headers=h, json={}).status_code == 404


def test_investors_do_not_see_figures_yet(client, make_company, invite):
    company = make_company()
    investor = invite(company, "investor")
    assert (
        client.get("/company/metrics", headers=investor.auth(company.tenant_id)).status_code == 403
    )

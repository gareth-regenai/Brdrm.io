"""FRD chapter 6, FR-3.3 and FR-3.4: updates, approvals, edits, comments and the PDF.

An update is made by code when an upload is ready. It waits for an approver, then every
investor sees it. It can be edited after that, and shows "Last edited".
"""

import base64
import os
import re
import zlib
from pathlib import Path

import psycopg
import pytest

from boardroom.modules.notify.mailer import memory_mailer
from boardroom.modules.updates import pdf
from tests.conftest import png_data_url, upload_file

SNAPSHOTS = Path(__file__).parent / "fixtures" / "snapshots"


def _h(account, company):
    return account.auth(company.tenant_id)


def _updates(client, account, company):
    r = client.get("/company/updates", headers=_h(account, company))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def shared_setup(client, make_company, invite, recorded_ai):
    """A company with a CEO and an investor, and one update from the CEO's P&L."""
    company = make_company("Kestrel Field")
    ceo = invite(company, "ceo")
    investor = invite(company, "investor")
    upload_file(client, company, "xero_pnl.csv", account=ceo)
    [update] = _updates(client, ceo, company)
    return company, ceo, investor, update


# FR-6.1, FR-3.4: each finished upload makes an update with the dated line


def test_a_finished_upload_makes_a_dated_update(client, shared_setup):
    company, ceo, _, update = shared_setup
    # xero_pnl.csv runs to September 2026, so its data is true as of the month end.
    assert f"{update['headline']}. {update['detail']}" == (
        "CEO ceo person added new financials. Data true as of 30 Sep 2026. "
        "Subject to change and may be edited."
    )
    assert update["status"] == "awaiting_approval"
    assert update["department"] == "finance"
    metrics = [f["metric"] for f in update["figures"]]
    # A P&L gives revenue and what follows from it. It has no cash balance.
    assert metrics == ["revenue", "revenue_growth", "gross_margin", "net_burn"]
    assert all(f["period"] == "2026-09" for f in update["figures"] if f["metric"] == "revenue")
    assert all("xero_pnl.csv" in f["source_line"] for f in update["figures"])


def test_the_upload_date_can_be_used_instead(client, make_company, recorded_ai, monkeypatch):
    from boardroom.config import get_settings

    monkeypatch.setattr(get_settings(), "update_as_of", "upload")
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    [update] = _updates(client, company.owner, company)
    assert "Data true as of 30 Sep 2026" not in update["detail"]


def test_phase_2_files_make_no_update_while_the_flag_is_off(client, make_company, recorded_ai):
    company = make_company()
    upload_file(client, company, "team_with_pay.csv")
    assert _updates(client, company.owner, company) == []


# FR-3.3, FR-6.3: investors see an update only once an approver acts


def test_an_investor_cannot_see_an_update_until_an_approver_acts(client, shared_setup):
    company, ceo, investor, update = shared_setup
    u = update["id"]
    assert _updates(client, investor, company) == []
    fig = update["figures"][0]["figure_id"]
    for method, path in (
        ("GET", f"/company/updates/{u}/figures/{fig}"),
        ("GET", f"/company/updates/{u}/pdf"),
        ("POST", f"/company/updates/{u}/comments"),
    ):
        r = client.request(method, path, headers=_h(investor, company), json={"body": "Hi"})
        assert r.status_code == 404, (path, r.status_code)

    r = client.post(f"/company/updates/{u}/approve", headers=_h(ceo, company))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "shared" and r.json()["approved_by_name"] == "ceo person"
    [seen] = _updates(client, investor, company)
    assert seen["id"] == u and seen["figures"] == update["figures"]
    assert seen["can_approve"] is False and seen["can_edit"] is False
    # The upload reaches its last state (FR-3.1).
    uploads = client.get("/company/uploads", headers=_h(ceo, company)).json()
    assert uploads[0]["status"] == "shared"
    assert client.post(f"/company/updates/{u}/approve", headers=_h(ceo, company)).status_code == 409


def test_the_database_hides_unshared_updates_from_investors(shared_setup, owner_conn):
    """Below the API: an investor's session reads no update awaiting approval."""
    company, ceo, investor, update = shared_setup

    def visible(account):
        with psycopg.connect(owner_conn.info.dsn, password=owner_conn.info.password) as conn:
            conn.execute("SET ROLE br_app")
            conn.execute("SELECT set_config('app.tenant_id', %s, false)", (company.tenant_id,))
            conn.execute("SELECT set_config('app.user_id', %s, false)", (account.user_id,))
            return [
                conn.execute(f"SELECT count(*) FROM updates.{t}").fetchone()[0]  # noqa: S608
                for t in ("updates", "figures")
            ]

    assert visible(ceo)[0] == 1 and visible(ceo)[1] > 0
    assert visible(investor) == [0, 0]
    owner_conn.execute("UPDATE updates.updates SET status = 'shared'")
    assert visible(investor)[0] == 1


def test_who_can_approve_follows_the_company_setting(client, shared_setup, invite):
    company, ceo, _, update = shared_setup
    lead = invite(company, "department_lead", ["finance"])
    u = update["id"]
    assert _updates(client, lead, company)[0]["can_approve"] is False
    assert (
        client.post(f"/company/updates/{u}/approve", headers=_h(lead, company)).status_code == 403
    )
    client.put(
        "/company/settings/approval",
        headers=_h(company.owner, company),
        json={"roles": ["ceo"], "user_ids": [lead.user_id]},
    )
    assert _updates(client, lead, company)[0]["can_approve"] is True
    assert (
        client.post(f"/company/updates/{u}/approve", headers=_h(lead, company)).status_code == 200
    )


# FR-2.3: standing access


def test_an_investor_invited_later_sees_every_shared_update(client, shared_setup, invite):
    company, ceo, _, update = shared_setup
    client.post(f"/company/updates/{update['id']}/approve", headers=_h(ceo, company))
    late = invite(company, "investor")
    assert [u["id"] for u in _updates(client, late, company)] == [update["id"]]


def test_approvers_hear_of_a_new_update_and_investors_of_a_shared_one(
    client, make_company, invite, recorded_ai
):
    company = make_company("Kestrel Field")
    ceo = invite(company, "ceo")
    investor = invite(company, "investor")
    memory_mailer().sent.clear()
    upload_file(client, company, "xero_pnl.csv")  # the Owner adds it, the CEO approves
    waiting = [e for e in memory_mailer().sent if "waiting for approval" in e.subject]
    assert [e.to for e in waiting] == [ceo.email]
    assert "added new financials" in waiting[0].body
    [update] = _updates(client, ceo, company)
    client.post(f"/company/updates/{update['id']}/approve", headers=_h(ceo, company))
    shared = [e for e in memory_mailer().sent if e.subject == "New update from Kestrel Field"]
    assert [e.to for e in shared] == [investor.email]


# FR-6.2: edit after sharing, "Last edited", audit before and after


def test_editing_a_figure_shows_last_edited_to_the_investor_and_is_audited(
    client, shared_setup, owner_conn
):
    company, ceo, investor, update = shared_setup
    u = update["id"]
    client.post(f"/company/updates/{u}/approve", headers=_h(ceo, company))
    revenue = next(f for f in update["figures"] if f["metric"] == "revenue")
    r = client.put(
        f"/company/updates/{u}/figures/{revenue['figure_id']}",
        headers=_h(ceo, company),
        json={"value": "80,000"},
    )
    assert r.status_code == 200, r.text

    [seen] = _updates(client, investor, company)
    assert seen["last_edited_at"] is not None and seen["last_edited_by_name"] == "ceo person"
    changed = next(f for f in seen["figures"] if f["metric"] == "revenue")
    # Formatted by code, at the company's precision.
    assert changed["display"] == "£80.0k"
    assert changed["calculated_display"] == revenue["display"]
    assert changed["edited_by_name"] == "ceo person"

    trace = client.get(
        f"/company/updates/{u}/figures/{revenue['figure_id']}", headers=_h(investor, company)
    ).json()
    assert trace["value"] == "80000" and trace["edited"]["by"] == "ceo person"
    assert trace["sources"][0]["filename"] == "xero_pnl.csv"

    (details,) = owner_conn.execute(
        "SELECT details FROM audit.audit_log WHERE action = 'update.edited'"
    ).fetchone()
    assert details["metric"] == "revenue" and details["after"] == "80000"
    assert details["before"] == trace["edited"]["calculated_value"]


def test_putting_back_the_calculated_figure(client, shared_setup):
    company, ceo, _, update = shared_setup
    fig = update["figures"][0]
    path = f"/company/updates/{update['id']}/figures/{fig['figure_id']}"
    client.put(path, headers=_h(ceo, company), json={"value": "1"})
    r = client.put(path, headers=_h(ceo, company), json={"value": None}).json()
    back = next(f for f in r["figures"] if f["figure_id"] == fig["figure_id"])
    assert back["display"] == fig["display"] and back["calculated_display"] is None


@pytest.mark.parametrize("value", ["eighty", "1e20", "NaN", "Infinity"])
def test_an_edit_must_be_a_number(client, shared_setup, value):
    company, ceo, _, update = shared_setup
    fig = update["figures"][0]["figure_id"]
    r = client.put(
        f"/company/updates/{update['id']}/figures/{fig}",
        headers=_h(ceo, company),
        json={"value": value},
    )
    assert r.status_code == 422


def test_a_department_lead_edits_only_their_own_sections(client, shared_setup, invite):
    company, _, _, update = shared_setup
    fig = update["figures"][0]["figure_id"]
    path = f"/company/updates/{update['id']}/figures/{fig}"
    sales = invite(company, "department_lead", ["sales"])
    finance = invite(company, "department_lead", ["finance"])
    assert _updates(client, sales, company)[0]["can_edit"] is False
    assert client.put(path, headers=_h(sales, company), json={"value": "1"}).status_code == 403
    assert client.put(path, headers=_h(finance, company), json={"value": "1"}).status_code == 200


# FR-6.5: comments notify the other side


def test_an_investor_comment_notifies_the_ceo_and_the_reply_notifies_the_investor(
    client, shared_setup
):
    company, ceo, investor, update = shared_setup
    u = update["id"]
    client.post(f"/company/updates/{u}/approve", headers=_h(ceo, company))
    memory_mailer().sent.clear()
    r = client.post(
        f"/company/updates/{u}/comments",
        headers=_h(investor, company),
        json={"body": "Is the Q4 pipeline all enterprise?"},
    )
    assert r.status_code == 200, r.text
    to_company = {e.to for e in memory_mailer().sent}
    assert to_company == {ceo.email, company.owner.email}
    assert "Is the Q4 pipeline all enterprise?" in memory_mailer().sent[0].body

    memory_mailer().sent.clear()
    r = client.post(
        f"/company/updates/{u}/comments",
        headers=_h(ceo, company),
        json={"body": "Two enterprise deals, the rest mid-market."},
    )
    assert {e.to for e in memory_mailer().sent} == {investor.email}
    thread = [(c["author_name"], c["author_role"], c["mine"]) for c in r.json()["comments"]]
    assert thread == [("investor person", "investor", False), ("ceo person", "ceo", True)]


def test_a_comment_on_an_unshared_update_tells_no_investor(client, shared_setup):
    company, ceo, _, update = shared_setup
    memory_mailer().sent.clear()
    client.post(
        f"/company/updates/{update['id']}/comments", headers=_h(ceo, company), json={"body": "Hi"}
    )
    assert memory_mailer().sent == []


def test_an_empty_comment_is_refused(client, shared_setup):
    company, ceo, _, update = shared_setup
    r = client.post(
        f"/company/updates/{update['id']}/comments", headers=_h(ceo, company), json={"body": "  "}
    )
    assert r.status_code == 422


# FR-6.7: every figure in an update traces to its source


def test_a_figure_not_in_the_update_is_not_traced(client, shared_setup):
    company, ceo, _, update = shared_setup
    other = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/company/updates/{update['id']}/figures/{other}", headers=_h(ceo, company))
    assert r.status_code == 404


# FR-6.6: PDF with the company's logo and colours


def _pdf_text(data: bytes) -> str:
    out = []
    for stream in re.findall(rb"stream\r?\n(.*?)\s*endstream", data, re.S):
        try:  # ReportLab writes ASCII85 over Flate
            raw = base64.a85decode(stream.strip().removesuffix(b"~>"))
            out.append(zlib.decompress(raw).decode("latin-1"))
        except (ValueError, zlib.error):
            continue
    return "\n".join(out)


def _document(**kw):
    base = dict(
        company_name="Kestrel Field",
        colour="#1F5F8F",
        logo=None,
        headline="CEO Sam Hart added new financials",
        detail="Data true as of 30 Sep 2026. Subject to change and may be edited.",
        labels=["Approved by Sam Hart, 18 Oct 2026"],
        figures=[
            pdf.FigureLine("Cash", "2026-09", "£1.378m", '=HYPERLINK("x") <b>.csv, 12 rows'),
            pdf.FigureLine(
                "Net burn", "2026-09", "-£17.1k", "finance.csv, 3 rows", "Changed by Sam"
            ),
        ],
    )
    base.update(kw)
    return pdf.UpdateDocument(**base)


def test_the_pdf_matches_its_snapshot():
    logo = base64.b64decode(png_data_url().split(",", 1)[1])
    data = pdf.render(_document(logo=logo))
    path = SNAPSHOTS / "update.pdf"
    if os.environ.get("UPDATE_SNAPSHOTS"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    assert data == path.read_bytes(), "run with UPDATE_SNAPSHOTS=1 after a deliberate change"


def test_the_pdf_neutralises_formula_injection_and_markup():
    text = _pdf_text(pdf.render(_document()))
    # The file name starts with "=", so it is neutralised with a leading quote.
    assert "(Source: '=HYPERLINK" in text
    # Markup in a file name is printed as text, never applied.
    assert '(Source: \'=HYPERLINK\\("x"\\) <) Tj (b) Tj (>) Tj' in text
    # One figure was changed by hand, so the footer does not claim they all came from code.
    assert "except where a" in text
    # A negative figure is code's own output: printed as it is, not mistaken for a formula.
    assert "(-\\24317.1k) Tj" in text


def test_the_pdf_text_reads_on_any_brand_colour():
    assert pdf._on(pdf.colors.HexColor("#123C4A")) == pdf.WHITE
    assert pdf._on(pdf.colors.HexColor("#F5D76E")) == pdf.INK


def test_an_update_downloads_as_a_pdf(client, shared_setup, owner_conn):
    company, ceo, investor, update = shared_setup
    h = _h(company.owner, company)
    client.put("/company/settings/profile", headers=h, json={"brand_colour": "#1f5f8f"})
    r = client.put("/company/settings/logo", headers=h, json={"data_url": png_data_url()})
    assert r.status_code == 200
    client.post(f"/company/updates/{update['id']}/approve", headers=_h(ceo, company))
    r = client.get(f"/company/updates/{update['id']}/pdf", headers=_h(investor, company))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "Kestrel%20Field%20update%202026-09-30.pdf" in r.headers["content-disposition"]
    assert "/Subtype /Image" in r.content.decode("latin-1")  # the logo is in it
    assert (
        owner_conn.execute(
            "SELECT count(*) FROM audit.audit_log WHERE action = 'update.exported'"
        ).fetchone()[0]
        == 1
    )


# The logo and colour


def test_the_logo_is_checked_and_redrawn_as_a_png(client, make_company):
    company = make_company()
    h = _h(company.owner, company)
    r = client.put("/company/settings/logo", headers=h, json={"data_url": png_data_url((900, 300))})
    assert r.status_code == 200 and r.json()["has_logo"] is True
    image = client.get("/company/settings/logo", headers=h)
    assert image.content.startswith(b"\x89PNG")
    import io

    from PIL import Image

    assert Image.open(io.BytesIO(image.content)).size == (600, 200)
    assert client.delete("/company/settings/logo", headers=h).json()["has_logo"] is False
    assert client.get("/company/settings/logo", headers=h).status_code == 404


@pytest.mark.parametrize(
    "data_url",
    [
        "data:image/png;base64,bm90IGFuIGltYWdl",  # "not an image"
        "data:image/png;base64,***",
        "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
    ],
)
def test_a_file_that_is_not_a_logo_is_refused(client, make_company, data_url):
    company = make_company()
    r = client.put(
        "/company/settings/logo", headers=_h(company.owner, company), json={"data_url": data_url}
    )
    assert r.status_code == 422


def test_a_brand_colour_must_be_a_hex_colour(client, make_company):
    company = make_company()
    h = _h(company.owner, company)
    assert (
        client.put("/company/settings/profile", headers=h, json={"brand_colour": "red"}).status_code
        == 422
    )
    r = client.put("/company/settings/profile", headers=h, json={"brand_colour": "#1f5f8f"})
    assert r.json()["brand_colour"] == "#1F5F8F"
    r = client.put("/company/settings/profile", headers=h, json={"brand_colour": ""})
    assert r.json()["brand_colour"] is None

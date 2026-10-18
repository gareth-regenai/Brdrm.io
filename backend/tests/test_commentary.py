"""FR-5.5, FR-6.4 and FR-10.3: commentary and the number check.

Claude's answers are recorded here: each test says what skill 3 answers, built from the
facts it was given, and checks what code does with it. Nothing calls the live API.
"""

import json
from decimal import Decimal

import pytest

from boardroom.modules.insights import skill3
from boardroom.modules.insights.check import Candidate, check
from tests.conftest import upload_file


def _facts(payload):
    text = payload["messages"][0]["content"]
    return json.loads(text.split("<facts>\n", 1)[1].rsplit("\n</facts>", 1)[0])


def _shown(facts, measure):
    return next(f["shown_as"] for f in facts["figures"] if f["measure"] == measure)


def good(facts):
    """A draft that writes figures exactly as code showed them."""
    return {
        "headline": f"Revenue was {_shown(facts, 'Revenue')} in September.",
        "notes": [
            {
                "department": "finance",
                "text": f"Gross margin held at {_shown(facts, 'Gross margin')}, and net "
                f"monthly burn was {_shown(facts, 'Net monthly burn')} over the last 3 months.",
            }
        ],
        "board_questions": ["What is driving the margin?"],
    }


class Recorded:
    model = "recorded"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.payloads = []

    def interpret(self, payload):
        self.payloads.append(payload)
        answer = self.answers.pop(0)
        return answer(_facts(payload)) if callable(answer) else answer


@pytest.fixture
def claude():
    def install(*answers):
        client = Recorded(*answers)
        skill3.set_client(client)
        return client

    return install


def _h(account, company):
    return account.auth(company.tenant_id)


def _update(client, account, company):
    [u] = client.get("/company/updates", headers=_h(account, company)).json()
    return u


def _section(update, kind):
    return next(s for s in update["sections"] if s["kind"] == kind)


# FR-5.5: the number check


CASH = Candidate("money", Decimal(1378000), "Cash, Sep 2026")


@pytest.mark.parametrize(
    "text, passed",
    [
        ("Cash is about £1.4m.", True),  # the FRD's own example
        ("Cash is £1.5m.", False),
        ("Two deals should sign by 12 December.", True),  # a date is ignored
        ("Cash is £1.378m.", True),
        ("Cash is £1.38m.", True),
        ("Cash is £1,378,000.", True),
        ("Cash is £1,378k.", True),
        ("Cash is £1.37m.", False),  # rounded the wrong way
        ("Cash is £1.379m.", False),
        ("Cash is €1.4m.", False),  # the wrong currency
        ("Cash is 1.4 million.", True),
        ("In Q3 we hired 2 people over the last 3 months.", True),  # quarters and counts
        ("Our 2026 plan is on track.", True),  # a year
    ],
)
def test_the_number_check(text, passed):
    assert check(text, [CASH]).passed is passed


@pytest.mark.parametrize(
    "text, passed",
    [
        ("Runway is 17.6 months.", True),
        ("Runway is 17.7 months.", False),
        ("Runway fell 1.5 months.", True),  # the change from last period
        ("Runway fell 1.6 months.", False),
        ("Revenue was 92% of plan.", True),  # 91.56% rounded to a whole number
        ("Revenue was 91.6% of plan.", True),
        ("Revenue was 91.5% of plan.", False),
        ("Coverage is 2.4x.", True),
        ("Coverage is 2.5x.", False),
    ],
)
def test_the_number_check_knows_each_unit(text, passed):
    candidates = [
        Candidate("months", Decimal("17.6"), "Runway, Sep 2026"),
        Candidate("months", Decimal("-1.5"), "Change in runway"),
        Candidate("percent", Decimal("0.9156"), "Revenue as a share of target"),
        Candidate("ratio", Decimal("2.4"), "Coverage, Sep 2026"),
    ]
    assert check(text, candidates).passed is passed


def test_a_figure_cannot_borrow_another_units_value():
    """2.4 is a ratio here, so "2.4 months" and "£2.4" match nothing."""
    ratio = [Candidate("ratio", Decimal("2.4"), "Coverage")]
    assert not check("Runway is 2.4 months.", ratio).passed
    assert not check("Burn was £2.4.", ratio).passed


# Drafting: Claude writes, code checks


def test_a_draft_that_passes_is_kept_and_labelled(client, make_company, recorded_ai, claude):
    model = claude(good)
    company = make_company("Kestrel Field")
    up = upload_file(client, company, "xero_pnl.csv")
    assert up["status"] == "ready"
    update = _update(client, company.owner, company)
    headline = _section(update, "headline")
    assert headline["text"] == "Revenue was £72.9k in September."
    assert headline["label"] == "Drafted by Claude" and headline["status"] == "drafted"
    assert _section(update, "note")["unmatched"] == []
    assert len(model.payloads) == 1  # passed first time, no redraft


def test_skill_3_sees_figures_only(client, make_company, recorded_ai, claude):
    """FR-10.3: computed figures, last period, targets and risk. No rows, files or people."""
    model = claude(good)
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    payload = model.payloads[0]
    facts = _facts(payload)
    assert set(facts) == {"company", "currency", "data_true_as_of", "departments", "figures"}
    allowed = {
        "measure",
        "period",
        "shown_as",
        "exact",
        "risk_level",
        "last_period",
        "change_from_last_period",
        "calculated_from",
        "share_of_target",
    }
    for f in facts["figures"]:
        assert set(f) <= allowed
    text = json.dumps(payload)
    assert "xero_pnl" not in text and "Total Trading Income" not in text
    revenue = next(f for f in facts["figures"] if f["measure"] == "Revenue")
    assert revenue["last_period"]["period"] == "Aug 2026"


def test_a_failed_draft_is_redrafted_once_with_the_differences(
    client, make_company, recorded_ai, claude
):
    wrong = {
        "headline": "Revenue was £99.9k in September.",
        "notes": [{"department": "finance", "text": "A steady month."}],
        "board_questions": [],
    }
    model = claude(wrong, good)
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    assert len(model.payloads) == 2
    retry = model.payloads[1]["messages"]
    assert retry[1]["role"] == "assistant" and "£99.9k" in retry[1]["content"]
    assert "£99.9k" in retry[2]["content"] and "headline" in retry[2]["content"]
    update = _update(client, company.owner, company)
    assert _section(update, "headline")["text"] == "Revenue was £72.9k in September."


def test_a_section_that_fails_twice_waits_for_a_person(
    client, make_company, invite, recorded_ai, claude
):
    def half_wrong(facts):
        answer = good(facts)
        answer["notes"][0]["text"] = "Net monthly burn was £1.0m."
        return answer

    claude(half_wrong, half_wrong)
    company = make_company()
    ceo = invite(company, "ceo")
    investor = invite(company, "investor")
    upload_file(client, company, "xero_pnl.csv")
    update = _update(client, ceo, company)
    note = _section(update, "note")
    assert note["text"] is None and note["status"] == "needs_person"
    assert "did not pass the number check twice" in note["reason"]
    assert note["unmatched"] == ["£1.0m"]
    assert _section(update, "headline")["status"] == "drafted"  # the part that passed stays

    client.post(f"/company/updates/{update['id']}/approve", headers=_h(ceo, company))
    seen = _update(client, investor, company)
    assert [s["kind"] for s in seen["sections"]] == ["headline"]  # nothing unchecked

    r = client.put(
        f"/company/updates/{update['id']}/sections/{note['id']}",
        headers=_h(ceo, company),
        json={"text": "Burn came down after the office move."},
    )
    assert r.status_code == 200, r.text
    written = _section(r.json(), "note")
    assert written["label"] == "Written by ceo person" and written["status"] == "written"
    assert _section(_update(client, investor, company), "note")["text"].startswith("Burn came")


def test_without_claude_every_section_waits_for_a_person(client, make_company, recorded_ai):
    company = make_company()
    up = upload_file(client, company, "xero_pnl.csv")
    assert up["status"] == "ready"
    update = _update(client, company.owner, company)
    assert {s["status"] for s in update["sections"]} == {"needs_person"}
    assert update["sections"][0]["reason"] == "Claude is switched off."


@pytest.mark.parametrize(
    "bad",
    [
        {"headline": "Hi", "notes": [], "board_questions": [], "revenue": "1"},
        {"headline": "", "notes": [], "board_questions": []},
        {"headline": "Hi", "notes": [{"department": "sales", "text": "x"}], "board_questions": []},
        {"headline": "Hi", "notes": [{"department": "finance"}], "board_questions": []},
        {"headline": "Hi", "notes": [], "board_questions": ["a", "b", "c", "d", "e", "f"]},
        {"headline": "Hi", "notes": "finance", "board_questions": []},
        ["Hi"],
    ],
)
def test_skill_3_output_outside_the_schema_is_refused(bad):
    with pytest.raises(skill3.CommentaryOutputError):
        skill3.validate(bad, ["finance"])


def test_an_answer_outside_the_schema_counts_as_a_failed_draft(
    client, make_company, recorded_ai, claude
):
    model = claude({"headline": "Hi", "figures": []}, good)
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    assert len(model.payloads) == 2
    assert _section(_update(client, company.owner, company), "headline")["status"] == "drafted"


# FR-6.4: voice and labels


def test_switching_the_voice_changes_the_next_draft(client, make_company, recorded_ai, claude):
    model = claude(good, good)
    company = make_company("Kestrel Field")
    h = _h(company.owner, company)
    upload_file(client, company, "xero_pnl.csv")
    assert '"we"' in model.payloads[0]["system"]
    client.put("/company/settings/profile", headers=h, json={"voice": "third_person"})
    update = _update(client, company.owner, company)
    r = client.post(f"/company/updates/{update['id']}/redraft", headers=h)
    assert r.status_code == 200, r.text
    second = model.payloads[1]["system"]
    assert "third person" in second and "Kestrel Field's" in second
    assert all(s["label"] for s in r.json()["sections"])  # labels always show


def test_editing_claudes_draft_is_labelled_and_checked(
    client, make_company, recorded_ai, claude, owner_conn
):
    claude(good)
    company = make_company()
    h = _h(company.owner, company)
    upload_file(client, company, "xero_pnl.csv")
    update = _update(client, company.owner, company)
    headline = _section(update, "headline")
    r = client.put(
        f"/company/updates/{update['id']}/sections/{headline['id']}",
        headers=h,
        json={"text": "Revenue was about £1.0m in September."},
    )
    edited = _section(r.json(), "headline")
    assert edited["label"] == "Drafted by Claude, edited by Owner of " + company.name
    # A person may write what they like, but the company is shown what matches nothing.
    assert edited["unmatched"] == ["£1.0m"]
    assert r.json()["last_edited_at"] is not None
    (details,) = owner_conn.execute(
        "SELECT details FROM audit.audit_log WHERE action = 'update.commentary_edited'"
    ).fetchone()
    assert details["before"] == headline["text"] and details["after"].startswith("Revenue was")


def test_a_redraft_keeps_what_a_person_wrote(client, make_company, recorded_ai, claude):
    model = claude(good, good)
    company = make_company()
    h = _h(company.owner, company)
    upload_file(client, company, "xero_pnl.csv")
    update = _update(client, company.owner, company)
    note = _section(update, "note")
    client.put(
        f"/company/updates/{update['id']}/sections/{note['id']}",
        headers=h,
        json={"text": "Our own words."},
    )
    r = client.post(f"/company/updates/{update['id']}/redraft", headers=h).json()
    assert _section(r, "note")["text"] == "Our own words."
    assert len(model.payloads) == 2


# What investors see


def test_board_questions_stay_with_the_company(
    client, make_company, invite, recorded_ai, claude, owner_conn
):
    import psycopg

    claude(good)
    company = make_company()
    investor = invite(company, "investor")
    upload_file(client, company, "xero_pnl.csv")
    update = _update(client, company.owner, company)
    assert _section(update, "questions")["text"] == "What is driving the margin?"
    client.post(f"/company/updates/{update['id']}/approve", headers=_h(company.owner, company))
    seen = _update(client, investor, company)
    assert {s["kind"] for s in seen["sections"]} == {"headline", "note"}
    assert all(s["reason"] is None and s["unmatched"] == [] for s in seen["sections"])
    # The database agrees.
    with psycopg.connect(owner_conn.info.dsn, password=owner_conn.info.password) as conn:
        conn.execute("SET ROLE br_app")
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (company.tenant_id,))
        conn.execute("SELECT set_config('app.user_id', %s, false)", (investor.user_id,))
        kinds = conn.execute("SELECT kind FROM updates.sections").fetchall()
    assert sorted(k for (k,) in kinds) == ["headline", "note"]


def test_the_trace_says_how_the_commentary_wrote_the_figure(
    client, make_company, recorded_ai, claude
):
    claude(good)
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    update = _update(client, company.owner, company)
    revenue = next(f for f in update["figures"] if f["metric"] == "revenue")
    trace = client.get(
        f"/company/updates/{update['id']}/figures/{revenue['figure_id']}",
        headers=_h(company.owner, company),
    ).json()
    assert trace["check"] == "Passed. The commentary writes it as £72.9k."
    growth = next(f for f in update["figures"] if f["metric"] == "revenue_growth")
    trace = client.get(
        f"/company/updates/{update['id']}/figures/{growth['figure_id']}",
        headers=_h(company.owner, company),
    ).json()
    assert trace["check"] == "Not written in this update's commentary."


def test_the_pdf_carries_the_commentary_and_who_wrote_it(client, make_company, recorded_ai, claude):
    from tests.test_updates import _pdf_text

    claude(good)
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    update = _update(client, company.owner, company)
    r = client.get(f"/company/updates/{update['id']}/pdf", headers=_h(company.owner, company))
    text = _pdf_text(r.content)
    assert "(Revenue was \\24372.9k in September.) Tj" in text
    assert "Drafted by Claude" in text
    assert "What is driving the margin" not in text


def test_the_recorded_draft_for_local_demos(client, make_company, recorded_ai, monkeypatch):
    """Development only, matched on the exact figures. Other files fall back to a person."""
    from pathlib import Path

    from boardroom.config import get_settings

    recorded = Path(__file__).parent / "fixtures" / "recorded"
    monkeypatch.setattr(get_settings(), "skill1_replay_dir", str(recorded))
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    update = _update(client, company.owner, company)
    assert _section(update, "headline")["text"] == "Revenue grew 3.5% to £72.9k in September."
    assert {s["status"] for s in update["sections"]} == {"drafted"}

    other = make_company()
    upload_file(client, other, "quickbooks_monthly.csv")
    statuses = {s["status"] for s in _update(client, other.owner, other)["sections"]}
    assert statuses == {"needs_person"}

"""The board pack ("The Full Picture") and @mentions in comments.

The company and its investors see the same pack. Investors see what was shared; the
company also sees what waits for approval, marked as such. Comments can tag people.
"""

import pytest

from boardroom.modules.insights import skill3
from boardroom.modules.notify.mailer import memory_mailer
from tests.conftest import upload_file
from tests.test_commentary import Recorded


def _h(account, company):
    return account.auth(company.tenant_id)


@pytest.fixture
def kestrel(client, make_company, invite, recorded_ai):
    """A company with a CEO, an investor and a contributor, and one update not yet shared.
    Revenue has a September target, so revenue against plan is calculated."""

    def note(facts):
        return {
            "headline": "Revenue was "
            + next(f["shown_as"] for f in facts["figures"] if f["measure"] == "Revenue")
            + " in September.",
            "notes": [{"department": "finance", "text": "A steady month."}],
            "board_questions": ["Why?"],
        }

    skill3.set_client(Recorded(note))
    company = make_company("Kestrel Field")
    ceo = invite(company, "ceo")
    investor = invite(company, "investor")
    contributor = invite(company, "contributor", ["finance"])
    client.put(
        "/company/settings/targets",
        headers=_h(ceo, company),
        json=[{"metric": "revenue", "period": "2026-09", "value": "70000"}],
    )
    upload_file(client, company, "quickbooks_monthly.csv", account=ceo)
    [update] = client.get("/company/updates", headers=_h(ceo, company)).json()
    return company, ceo, investor, contributor, update


def _pack(client, account, company):
    r = client.get("/company/pack", headers=_h(account, company))
    assert r.status_code == 200, r.text
    return r.json()


def test_the_company_sees_what_waits_and_investors_do_not(client, kestrel):
    company, ceo, investor, _, update = kestrel
    mine = _pack(client, ceo, company)
    assert mine["company_name"] == "Kestrel Field"
    assert mine["includes_unshared"] is True and mine["data_as_of"] == "2026-09-30"
    assert {f["shared"] for f in mine["figures"]} == {False}
    theirs = _pack(client, investor, company)
    assert theirs["figures"] == [] and theirs["series"] == [] and theirs["commentary"] == []
    assert theirs["includes_unshared"] is False and theirs["data_as_of"] is None

    client.post(f"/company/updates/{update['id']}/approve", headers=_h(ceo, company))
    theirs = _pack(client, investor, company)
    assert {f["shared"] for f in theirs["figures"]} == {True}
    # Same figures, same view: only the "shared" marks differ.
    strip = [{k: v for k, v in f.items() if k != "shared"} for f in mine["figures"]]
    assert [{k: v for k, v in f.items() if k != "shared"} for f in theirs["figures"]] == strip


def test_the_pack_has_monthly_series_targets_and_commentary(client, kestrel):
    company, ceo, *_ = kestrel
    pack = _pack(client, ceo, company)
    revenue = next(s for s in pack["series"] if s["metric"] == "revenue")
    assert [p["period"] for p in revenue["points"]] == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]
    assert revenue["points"][-1]["display"] == "£68.5k"
    assert {s["metric"] for s in pack["series"]} == {"revenue", "net_burn", "cash_balance"}
    [target] = pack["targets"]
    assert target["actual_display"] == "£68.5k" and target["target_display"] == "£70.0k"
    [finance] = pack["commentary"]
    assert finance["department"] == "finance"
    kinds = [s["kind"] for s in finance["sections"]]
    assert kinds == ["headline", "note"]  # never the board questions
    assert finance["sections"][0]["label"] == "Drafted by Claude"


# @mentions


def test_tagging_a_person_emails_them_once(client, kestrel):
    company, ceo, investor, _, update = kestrel
    client.post(f"/company/updates/{update['id']}/approve", headers=_h(ceo, company))
    memory_mailer().sent.clear()
    r = client.post(
        f"/company/updates/{update['id']}/comments",
        headers=_h(investor, company),
        json={"body": "@ceo person can you explain the burn?", "mentions": [ceo.user_id]},
    )
    assert r.status_code == 200, r.text
    to_ceo = [e for e in memory_mailer().sent if e.to == ceo.email]
    assert (
        len(to_ceo) == 1 and to_ceo[0].subject == "investor person mentioned you on Kestrel Field"
    )
    assert {e.to for e in memory_mailer().sent} == {ceo.email, company.owner.email}
    comment = r.json()["comments"][-1]
    assert comment["mentions"] == [{"user_id": ceo.user_id, "name": "ceo person"}]


def test_who_can_be_tagged(client, kestrel):
    company, ceo, investor, contributor, update = kestrel
    as_investor = {
        p["user_id"] for p in client.get("/company/people", headers=_h(investor, company)).json()
    }
    as_ceo = {p["user_id"] for p in client.get("/company/people", headers=_h(ceo, company)).json()}
    # An investor can tag the people who run the company, never the whole team.
    assert ceo.user_id in as_investor and contributor.user_id not in as_investor
    assert contributor.user_id in as_ceo and investor.user_id in as_ceo


@pytest.mark.parametrize(
    "who, body, why",
    [
        ("contributor", "@contributor person hello", "choosing them from the list"),
        ("ceo", "hello", "choosing them from the list"),  # tagged without writing @Name
    ],
)
def test_an_investor_cannot_tag_outside_their_list(client, kestrel, who, body, why):
    company, ceo, investor, contributor, update = kestrel
    client.post(f"/company/updates/{update['id']}/approve", headers=_h(ceo, company))
    target = {"contributor": contributor, "ceo": ceo}[who]
    r = client.post(
        f"/company/updates/{update['id']}/comments",
        headers=_h(investor, company),
        json={"body": body, "mentions": [target.user_id]},
    )
    assert r.status_code == 422 and why in r.json()["detail"]


def test_an_investor_cannot_be_tagged_before_they_can_see_the_update(client, kestrel):
    company, ceo, investor, _, update = kestrel
    r = client.post(
        f"/company/updates/{update['id']}/comments",
        headers=_h(ceo, company),
        json={"body": "@investor person look", "mentions": [investor.user_id]},
    )
    assert r.status_code == 422 and "once it is approved" in r.json()["detail"]

"""FR-12.4: structured logs with tenant ID and no data values."""

import json


def test_request_logs_are_json_with_tenant_and_no_values(client, make_company, capsys):
    company = make_company("Secretive Ltd")
    capsys.readouterr()
    client.get(
        f"/company/investors/{company.owner.user_id}x",
        headers=company.owner.auth(company.tenant_id),
    )
    client.get("/company", headers=company.owner.auth(company.tenant_id))
    lines = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    requests = [line for line in lines if line["event"] == "request"]
    assert requests
    last = requests[-1]
    assert last["tenant_id"] == company.tenant_id
    assert last["route"] == "/company"
    raw = json.dumps(lines)
    assert "Secretive Ltd" not in raw
    assert company.owner.access_token not in raw
    assert company.owner.email not in raw


def test_health_check(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}

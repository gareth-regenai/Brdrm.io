"""The committed API contract matches the code. Regenerate with scripts/export_openapi.py."""

from scripts.export_openapi import OUT, render


def test_openapi_contract_is_up_to_date():
    assert OUT.read_text() == render(), "run: python scripts/export_openapi.py"

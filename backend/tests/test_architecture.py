"""Structural rules checked in CI: module boundaries, reserved values, flags and hosting."""

import ast
import os
import re
from pathlib import Path

import yaml

from boardroom.config import FeatureFlags, Settings
from tests.routes import all_routes

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "backend" / "boardroom"
MODULES = PACKAGE / "modules"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names |= {f"{node.module}.{a.name}" for a in node.names}
        elif isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
    return names


def test_no_module_reads_another_modules_tables():
    # FR-10.2: modules may call each other's service functions, never their models.
    offences = []
    for module in [p for p in MODULES.iterdir() if p.is_dir() and p.name != "__pycache__"]:
        for path in module.rglob("*.py"):
            for name in _imports(path):
                m = re.match(r"boardroom\.modules\.(\w+)\.models", name)
                if m and m.group(1) != module.name:
                    offences.append(f"{path.relative_to(ROOT)} imports {name}")
    assert offences == []


def test_only_identity_reads_identity_tables_outside_the_modules():
    offences = []
    for path in PACKAGE.rglob("*.py"):
        if MODULES in path.parents or path.name == "worker.py":
            continue
        for name in _imports(path):
            if re.match(r"boardroom\.modules\.\w+\.models", name):
                offences.append(f"{path.relative_to(ROOT)} imports {name}")
    assert offences == []


SYSTEM_SESSION_ALLOWED = {
    # Before a user or tenant is known.
    ("modules/identity/service.py", "sign_in"),
    ("modules/identity/service.py", "refresh"),
    ("modules/identity/service.py", "sign_out"),
    # The dispatcher reads every module's outbox.
    ("events.py", "_dispatch_round"),
    # Platform admins reading the interpretation log (FR-4.10).
    ("modules/intake/api.py", "interpretation_log"),
}
AS_SYSTEM_ALLOWED = {
    # Joining a company once its invitation is checked.
    ("modules/identity/service.py", "sign_up"),
    ("modules/identity/service.py", "accept_invitation"),
    # Writing the interpretation log, which the app role cannot touch.
    ("modules/intake/pipeline.py", "_log"),
}


def _callers(name: str) -> set[tuple[str, str]]:
    found = set()
    for path in PACKAGE.rglob("*.py"):
        if path.name == "db.py":
            continue
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name:
                    found.add((str(path.relative_to(PACKAGE)), fn.name))
    return found


def test_system_role_is_used_only_where_listed():
    assert _callers("system_session") == SYSTEM_SESSION_ALLOWED
    assert _callers("as_system") == AS_SYSTEM_ALLOWED


def test_deal_team_is_used_by_no_route():
    # FR-2.9
    for path in PACKAGE.rglob("*.py"):
        if path.name == "permissions.py":
            continue
        assert "DEAL_TEAM" not in path.read_text() and "deal_team" not in path.read_text(), path
    assert all("deal" not in r.path for r in all_routes())


def test_phase_2_flags_are_off_by_default():
    # FR-1.3
    flags = FeatureFlags()
    assert not any(flags.model_dump().values())


def test_app_database_url_is_derived_for_the_login_role(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(
        migration_database_url="postgresql://owner:secret@db-host:5432/boardroom",
        app_db_password="p@ss/word",
    )
    assert (
        settings.database_url
        == "postgresql+psycopg://br_login:p%40ss%2Fword@db-host:5432/boardroom"
    )
    assert "owner" not in settings.database_url and "secret" not in settings.database_url


def _blueprint() -> dict:
    return yaml.safe_load((ROOT / "render.yaml").read_text())


def test_blueprint_pins_every_resource_to_frankfurt():
    # FR-12.1. Static sites are served from Render's CDN and take no region.
    bp = _blueprint()
    resources = [s for s in bp["services"] if s.get("runtime") != "static"] + bp["databases"]
    assert resources
    assert {r["name"]: r.get("region") for r in resources} == {
        r["name"]: "frankfurt" for r in resources
    }


def test_only_the_api_and_static_site_are_public():
    # FR-10.1
    bp = _blueprint()
    public = {s["name"] for s in bp["services"] if s["type"] == "web"}
    assert public == {"boardroom-api", "boardroom-web"}
    for s in bp["services"]:
        if s["type"] == "keyvalue":
            assert s["ipAllowList"] == []
    for db in bp["databases"]:
        assert db["ipAllowList"] == []


def test_blueprint_has_pull_request_previews():
    # FR-12.2
    assert _blueprint()["previews"]["generation"] == "automatic"


def test_no_secret_values_in_the_blueprint():
    text = (ROOT / "render.yaml").read_text()
    for line in text.splitlines():
        if re.search(r"(SECRET|PASSWORD|KEY)\b", line) and "value:" in line:
            raise AssertionError(f"secret value in render.yaml: {line.strip()}")
    assert os.path.exists(ROOT / "render.yaml")


def test_production_refuses_the_console_mailer(monkeypatch):
    from boardroom import config

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-secret-for-this-test")
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    for mailer, ok in (("console", False), ("disabled", True)):
        monkeypatch.setenv("MAILER", mailer)
        config.get_settings.cache_clear()
        try:
            config.get_settings()
            assert ok, mailer
        except RuntimeError:
            assert not ok, mailer
    config.get_settings.cache_clear()

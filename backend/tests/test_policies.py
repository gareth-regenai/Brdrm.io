"""FR-11.1: every table has row-level security, with a policy for the app role."""

SCHEMAS = ("identity", "audit", "events")


def test_every_table_has_row_level_security_and_an_app_policy(owner_conn):
    rows = owner_conn.execute(
        """
        SELECT n.nspname || '.' || c.relname, c.relrowsecurity,
               EXISTS (SELECT 1 FROM pg_policy p
                       WHERE p.polrelid = c.oid
                         AND (SELECT oid FROM pg_roles WHERE rolname = 'br_app') = ANY (p.polroles))
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r' AND n.nspname = ANY(%s)
        """,
        (list(SCHEMAS),),
    ).fetchall()
    assert rows, "no tables found"
    missing = [name for name, rls, policy in rows if not (rls and policy)]
    assert missing == []


def test_no_table_lives_outside_the_module_schemas(owner_conn):
    rows = owner_conn.execute(
        "SELECT schemaname || '.' || tablename FROM pg_tables "
        "WHERE schemaname NOT IN "
        "('pg_catalog', 'information_schema', 'identity', 'audit', 'events')"
    ).fetchall()
    assert [r for (r,) in rows] == ["public.alembic_version"]


def test_app_roles_cannot_bypass_row_level_security(owner_conn):
    rows = owner_conn.execute(
        "SELECT rolname, rolbypassrls, rolsuper FROM pg_roles "
        "WHERE rolname IN ('br_app', 'br_system', 'br_login')"
    ).fetchall()
    assert len(rows) == 3
    assert all(not bypass and not superuser for _, bypass, superuser in rows)


def test_login_role_has_no_table_rights_of_its_own(owner_conn):
    rows = owner_conn.execute(
        "SELECT table_schema, table_name FROM information_schema.role_table_grants "
        "WHERE grantee = 'br_login'"
    ).fetchall()
    assert rows == []

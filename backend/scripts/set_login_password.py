"""Sets the app's login password to APP_DB_PASSWORD. The first migration does this once;
docker compose runs this on every start too, because the test suite run against the same
database server changes it, and the app then cannot sign in."""

import os

import psycopg
from psycopg import sql

with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as conn:
    conn.execute(
        sql.SQL("ALTER ROLE br_login PASSWORD {}").format(
            sql.Literal(os.environ["APP_DB_PASSWORD"])
        )
    )

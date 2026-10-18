#!/usr/bin/env bash
# The restore drill (FR-12.3): back up a database, restore it into a fresh one, and prove
# every table came back whole, row for row. Prints how long the restore took.
#
#   SOURCE_URL=postgresql://owner:pw@host:5432/boardroom \
#   TARGET_DB=boardroom_restore_drill scripts/restore-drill.sh
#
# Run it against staging before launch and after any change to the database plan. The
# target is created on the same server, where the app's roles already exist; it is dropped
# first if it is there. Nothing is written to the source.
set -euo pipefail

: "${SOURCE_URL:?set SOURCE_URL to the owner connection of the database to back up}"
TARGET_DB="${TARGET_DB:-boardroom_restore_drill}"
SERVER_URL="${SOURCE_URL%/*}"
TARGET_URL="$SERVER_URL/$TARGET_DB"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Every application table, by schema, in a fixed order.
TABLES_SQL="SELECT schemaname || '.' || tablename FROM pg_tables
  WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1"
# Row count and a checksum of every row, independent of physical order.
fingerprint() {
  local url="$1"
  psql "$url" -At -c "$TABLES_SQL" | while read -r table; do
    psql "$url" -At -c "SELECT '$table', count(*),
      coalesce(md5(string_agg(md5(t::text), '' ORDER BY md5(t::text))), '-') FROM $table t"
  done
}

echo "Backing up $(basename "$SOURCE_URL")"
pg_dump --format=custom --file="$WORK/backup.dump" "$SOURCE_URL"
fingerprint "$SOURCE_URL" > "$WORK/source.txt"

psql "$SERVER_URL/postgres" -qc "DROP DATABASE IF EXISTS \"$TARGET_DB\" WITH (FORCE)" \
  -c "CREATE DATABASE \"$TARGET_DB\""
started=$(date +%s.%N)
pg_restore --exit-on-error --dbname="$TARGET_URL" "$WORK/backup.dump"
finished=$(date +%s.%N)
fingerprint "$TARGET_URL" > "$WORK/restored.txt"

tables=$(wc -l < "$WORK/source.txt")
rows=$(awk -F'|' '{s += $2} END {print s}' "$WORK/source.txt")
seconds=$(echo "$finished - $started" | bc)
if diff -u "$WORK/source.txt" "$WORK/restored.txt" > "$WORK/diff.txt"; then
  printf 'Restore drill passed: %s tables, %s rows, restored in %.1f seconds.\n' "$tables" "$rows" "$seconds"
else
  echo "Restore drill FAILED. Tables that differ:"
  grep '^[-+][a-z]' "$WORK/diff.txt" | cut -d'|' -f1 | sort -u
  exit 1
fi

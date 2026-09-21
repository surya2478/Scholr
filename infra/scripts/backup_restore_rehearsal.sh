#!/usr/bin/env bash
# Backup + restore rehearsal (PHASE-1 AC-O2). Dumps the dev database from the scholr-db container, restores it into a
# scratch database, and compares row counts table by table. The dump file stays inside the container (student data
# must never be copied into the repository). Run from the repo root: bash infra/scripts/backup_restore_rehearsal.sh
set -euo pipefail
# Git Bash on Windows rewrites container paths like /tmp/... into Windows paths; container paths must pass unchanged.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

CONTAINER="${CONTAINER:-scholr-db}"
DB_USER="${DB_USER:-scholr}"  # POSTGRES_USER in infra/docker-compose.yml
SOURCE_DB="${SOURCE_DB:-scholr}"
SCRATCH_DB="scholr_restore_rehearsal"
DUMP="/tmp/scholr_rehearsal.dump"
PSQL=(docker exec "$CONTAINER" psql -U "$DB_USER" -v ON_ERROR_STOP=1 -At)

TABLES=$("${PSQL[@]}" -d "$SOURCE_DB" -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")
count() { "${PSQL[@]}" -d "$1" -c "SET row_security = off; SELECT count(*) FROM \"$2\"" | tail -1; }
declare -A BEFORE
for t in $TABLES; do BEFORE[$t]=$(count "$SOURCE_DB" "$t"); done

echo "1/4 dump $SOURCE_DB"
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -Fc -f "$DUMP" "$SOURCE_DB"

echo "2/4 create $SCRATCH_DB"
"${PSQL[@]}" -c "DROP DATABASE IF EXISTS $SCRATCH_DB" -c "CREATE DATABASE $SCRATCH_DB"

echo "3/4 restore"
docker exec "$CONTAINER" pg_restore -U "$DB_USER" --no-owner --exit-on-error -d "$SCRATCH_DB" "$DUMP"

echo "4/4 compare row counts"
# The source may keep changing while the rehearsal runs (jobs writing telemetry), so the restored count must lie
# between the count taken before the dump and the count after the restore.
mismatch=0
for t in $TABLES; do
  restored=$(count "$SCRATCH_DB" "$t")
  after=$(count "$SOURCE_DB" "$t")
  lo=${BEFORE[$t]}; hi=$after
  if [ "$lo" -gt "$hi" ]; then lo=$after; hi=${BEFORE[$t]}; fi
  if [ "$restored" -lt "$lo" ] || [ "$restored" -gt "$hi" ]; then
    echo "  MISMATCH $t: restored $restored, source ${BEFORE[$t]} before / $after after"; mismatch=1
  elif [ "${BEFORE[$t]}" != "$after" ]; then
    echo "  note $t changed during the rehearsal (${BEFORE[$t]} -> $after); restored $restored is within range"
  fi
done

"${PSQL[@]}" -c "DROP DATABASE $SCRATCH_DB" >/dev/null
docker exec "$CONTAINER" rm -f "$DUMP"
if [ "$mismatch" -eq 0 ]; then
  echo "OK: restore matches the source ($(echo "$TABLES" | wc -w) tables) — record the date in docs/PHASE-1.md AC-O2"
else
  echo "FAILED: see mismatches above"; exit 1
fi

#!/bin/sh
set -eu

dump_path="${FACTOR_PLATFORM_ROADSHOW_SEED_DUMP:-/db_dumps/roadshow_demo.dump}"
seed_id="${FACTOR_PLATFORM_ROADSHOW_SEED_ID:-roadshow_demo}"
db_name="${POSTGRES_DB:-factor_platform}"
db_user="${POSTGRES_USER:-postgres}"

if [ ! -f "$dump_path" ]; then
  echo "roadshow db restore skipped: dump not found at $dump_path"
  exit 0
fi

checksum="$(sha256sum "$dump_path" | awk '{print $1}')"
current="$(psql -U "$db_user" -d "$db_name" -tAc "select dump_checksum from roadshow_seed_state where seed_id='${seed_id}'" 2>/dev/null | tr -d '[:space:]' || true)"

if [ "$current" = "$checksum" ]; then
  echo "roadshow db restore skipped: seed already restored ($checksum)"
  exit 0
fi

echo "restoring roadshow database from $dump_path"
pg_restore -U "$db_user" -d "$db_name" --clean --if-exists --no-owner "$dump_path"

psql -U "$db_user" -d "$db_name" <<SQL
insert into roadshow_seed_state (seed_id, dump_checksum, dump_path, restored_at, meta)
values ('${seed_id}', '${checksum}', '${dump_path}', now(), '{"restored_by":"roadshow_db_restore"}'::json)
on conflict (seed_id) do update set
  dump_checksum = excluded.dump_checksum,
  dump_path = excluded.dump_path,
  restored_at = now(),
  meta = excluded.meta;
SQL

echo "roadshow db restore complete: $checksum"

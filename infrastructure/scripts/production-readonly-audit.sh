#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME=${COMPOSE_PROJECT_NAME:-demand-gen-uploader}
CURRENT_LINK=${DGU_CURRENT_LINK:-/opt/demand-gen-uploader-current}
DATA_ROOT=${DGU_DATA_ROOT:-/opt/demand-gen-uploader}
BACKUP_ROOT=${BACKUP_ROOT:-/var/backups/demand-gen-uploader}

release_root=$(readlink -f "$CURRENT_LINK")
case "$release_root" in
  /opt/demand-gen-uploader-releases/*) ;;
  *) echo "audit_error|unexpected_release_root"; exit 2 ;;
esac
test -f "$release_root/.git-sha"
test -f "$release_root/docker-compose.yml"
test -f "$release_root/docker-compose.prod.yml"

compose=(docker compose -p "$PROJECT_NAME" -f "$release_root/docker-compose.yml" -f "$release_root/docker-compose.prod.yml")
release_sha=$(tr -d '\r\n' < "$release_root/.git-sha")
echo "release_sha|$release_sha"

services=(postgres redis api worker scheduler frontend reverse-proxy)
for service in "${services[@]}"; do
  container=$("${compose[@]}" ps -q "$service")
  test -n "$container"
  state=$(docker inspect --format '{{.State.Status}}' "$container")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container")
  restarts=$(docker inspect --format '{{.RestartCount}}' "$container")
  echo "container|$service|$state|$health|restarts=$restarts"
  test "$state" = "running"
  test "$health" = "healthy"
done

migration=$("${compose[@]}" exec -T api alembic current 2>&1 | tail -n 1 | tr -d '\r\n')
echo "migration|$migration"
echo "redis_ping|$("${compose[@]}" exec -T redis redis-cli ping | tr -d '\r\n')"
"${compose[@]}" exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null
echo "postgres_ready|true"

latest_backup=$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20??????-??????' | sort | tail -n 1)
test -n "$latest_backup"
(cd "$latest_backup" && sha256sum -c --quiet SHA256SUMS)
echo "backup|$latest_backup|checksums=verified"
echo "storage_files|$(find "$DATA_ROOT/storage" -type f | wc -l | tr -d ' ')"

sql=$(cat <<'SQL'
SELECT 'table_count', 'users', count(*)::text FROM users
UNION ALL SELECT 'table_count', 'google_connections', count(*)::text FROM google_connections
UNION ALL SELECT 'table_count', 'customer_accounts', count(*)::text FROM customer_accounts
UNION ALL SELECT 'table_count', 'campaign_uploads', count(*)::text FROM campaign_uploads
UNION ALL SELECT 'table_count', 'media_assets', count(*)::text FROM media_assets
UNION ALL SELECT 'table_count', 'deployment_plans', count(*)::text FROM deployment_plans
UNION ALL SELECT 'table_count', 'deployment_schedules', count(*)::text FROM deployment_schedules
UNION ALL SELECT 'table_count', 'control_center_saved_views', count(*)::text FROM control_center_saved_views
UNION ALL SELECT 'table_count', 'control_center_action_requests', count(*)::text FROM control_center_action_requests
UNION ALL SELECT 'table_count', 'audit_logs', count(*)::text FROM audit_logs
UNION ALL SELECT 'table_count', 'ai_conversations', count(*)::text FROM ai_conversations
UNION ALL SELECT 'table_count', 'ai_messages', count(*)::text FROM ai_messages
UNION ALL SELECT 'table_count', 'ai_runs', count(*)::text FROM ai_runs
UNION ALL SELECT 'table_count', 'ai_drafts', count(*)::text FROM ai_drafts
UNION ALL SELECT 'table_count', 'ai_saved_reports', count(*)::text FROM ai_saved_reports
ORDER BY 2;

SELECT 'admin', 'admin', count(*)::text
FROM users
WHERE username = 'admin' AND is_active IS TRUE;

SELECT 'connection', name, status, connection_mode,
       CASE WHEN last_error IS NULL OR last_error = '' THEN 'no_error' ELSE 'has_error' END
FROM google_connections
ORDER BY name;

SELECT 'connection_accounts', gc.name, count(ca.id)::text,
       (count(ca.id) FILTER (WHERE ca.is_test_account IS TRUE))::text
FROM google_connections gc
LEFT JOIN customer_accounts ca ON ca.connection_id = gc.id
GROUP BY gc.name
ORDER BY gc.name;

SELECT 'openai_key', 'database',
       CASE WHEN EXISTS (
         SELECT 1 FROM ai_admin_settings WHERE openai_key_encrypted IS NOT NULL
       ) THEN 'configured' ELSE 'not_configured' END;

WITH production_rows AS (
  SELECT count(*)::bigint AS amount FROM control_center_action_requests WHERE execution_mode = 'PRODUCTION'
  UNION ALL SELECT count(*)::bigint FROM deployment_plans WHERE execution_mode = 'PRODUCTION'
  UNION ALL SELECT count(*)::bigint FROM launch_batches WHERE execution_mode = 'PRODUCTION'
  UNION ALL SELECT count(*)::bigint FROM campaign_status_actions WHERE execution_mode = 'PRODUCTION'
)
SELECT 'production_mutate_count', 'persisted_production_operations', sum(amount)::text
FROM production_rows;
SQL
)
printf '%s\n' "$sql" | "${compose[@]}" exec -T postgres sh -c \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F "|"'

"${compose[@]}" exec -T api sh -c \
  'if [ -n "${OPENAI_API_KEY:-}" ]; then echo "openai_key|environment|configured"; else echo "openai_key|environment|not_configured"; fi'

problem_pattern='Traceback|ERROR|HTTP/[12][.][01]" 5[0-9][0-9]|OAuth[^[:space:]]* error|oauth[^[:space:]]* error'
for service in api worker scheduler redis reverse-proxy; do
  problem_lines=$("${compose[@]}" logs --since 5m --no-color "$service" 2>&1 | grep -Eic "$problem_pattern" || true)
  echo "log_problem_lines|$service|$problem_lines"
  test "$problem_lines" -eq 0
done

deployment_record="$DATA_ROOT/storage/system/deployments/$release_sha.json"
test -f "$deployment_record"
grep -q '"production_mutate_performed":false' "$deployment_record"
echo "deployment_record|healthy|production_mutate_performed=false"

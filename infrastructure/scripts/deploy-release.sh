#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

SHA=${1:-}
ARCHIVE=${2:-}
PROJECT_NAME=${COMPOSE_PROJECT_NAME:-demand-gen-uploader}
DATA_ROOT=${DGU_DATA_ROOT:-/opt/demand-gen-uploader}
RELEASES_ROOT=${DGU_RELEASES_ROOT:-/opt/demand-gen-uploader-releases}
CURRENT_LINK=${DGU_CURRENT_LINK:-/opt/demand-gen-uploader-current}
PUBLIC_URL=${DGU_PUBLIC_URL:-https://axyro.tech}
DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

case "$DATA_ROOT" in
  /opt/demand-gen-uploader) ;;
  *) echo "Refusing unexpected persistent data root." >&2; exit 2 ;;
esac
case "$RELEASES_ROOT" in
  /opt/demand-gen-uploader-releases) ;;
  *) echo "Refusing unexpected releases root." >&2; exit 2 ;;
esac
case "$CURRENT_LINK" in
  /opt/demand-gen-uploader-current) ;;
  *) echo "Refusing unexpected current-release link." >&2; exit 2 ;;
esac

if [[ ! "$SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "A full lowercase 40-character commit SHA is required." >&2
  exit 2
fi
if [[ ! -f "$ARCHIVE" ]]; then
  echo "Release archive is missing." >&2
  exit 2
fi
if [[ ! -f "$DATA_ROOT/.env" || ! -d "$DATA_ROOT/storage" ]]; then
  echo "Persistent environment or storage is missing." >&2
  exit 2
fi

available_kb=$(df -Pk "$(dirname "$RELEASES_ROOT")" 2>/dev/null | awk 'NR == 2 {print $4}' || true)
if [[ -n "$available_kb" && "$available_kb" -lt 2097152 ]]; then
  echo "At least 2 GiB of free disk space is required." >&2
  exit 2
fi

if tar -tzf "$ARCHIVE" | grep -Eq '(^/|(^|/)\.\.(/|$)|(^|/)\.env($|/))'; then
  echo "Unsafe path or environment file found in release archive." >&2
  exit 2
fi

mkdir -p "$RELEASES_ROOT" "$DATA_ROOT/storage/system/deployments"
release_dir="$RELEASES_ROOT/$SHA"
temporary_dir="$RELEASES_ROOT/.$SHA.tmp.$$"
rm -rf -- "$temporary_dir"
mkdir "$temporary_dir"
trap 'rm -rf -- "$temporary_dir"' EXIT
tar -xzf "$ARCHIVE" -C "$temporary_dir"
printf '%s\n' "$SHA" > "$temporary_dir/.git-sha"
ln -s "$DATA_ROOT/.env" "$temporary_dir/.env"
ln -s "$DATA_ROOT/storage" "$temporary_dir/storage"

if [[ -e "$release_dir" ]]; then
  test "$(cat "$release_dir/.git-sha")" = "$SHA"
  rm -rf -- "$temporary_dir"
else
  mv "$temporary_dir" "$release_dir"
fi
trap - EXIT

previous_root="$DATA_ROOT"
if [[ -L "$CURRENT_LINK" ]]; then
  previous_root=$(readlink -f "$CURRENT_LINK")
fi

APP_DIR="$previous_root" COMPOSE_PROJECT_NAME="$PROJECT_NAME" \
  "$previous_root/infrastructure/scripts/production-backup.sh"

old_image() {
  local service=$1
  local container
  container=$(docker ps -q \
    --filter "label=com.docker.compose.project=$PROJECT_NAME" \
    --filter "label=com.docker.compose.service=$service" | head -n 1)
  if [[ -n "$container" ]]; then
    docker inspect --format '{{.Image}}' "$container"
  fi
}

old_api=$(old_image api)
old_worker=$(old_image worker)
old_scheduler=$(old_image scheduler)
old_frontend=$(old_image frontend)

api_image="dgu-api:$SHA"
worker_image="dgu-worker:$SHA"
scheduler_image="dgu-scheduler:$SHA"
frontend_image="dgu-frontend:$SHA"

export APP_VERSION_SHA="$SHA"
export APP_RELEASE_TAG="manual-$SHA"
export APP_DEPLOYED_AT="$DEPLOYED_AT"
export DGU_API_IMAGE="$api_image"
export DGU_WORKER_IMAGE="$worker_image"
export DGU_SCHEDULER_IMAGE="$scheduler_image"
export DGU_FRONTEND_IMAGE="$frontend_image"

cat > "$release_dir/.deployment.env" <<EOF
APP_VERSION_SHA=$APP_VERSION_SHA
APP_RELEASE_TAG=$APP_RELEASE_TAG
APP_DEPLOYED_AT=$APP_DEPLOYED_AT
DGU_API_IMAGE=$DGU_API_IMAGE
DGU_WORKER_IMAGE=$DGU_WORKER_IMAGE
DGU_SCHEDULER_IMAGE=$DGU_SCHEDULER_IMAGE
DGU_FRONTEND_IMAGE=$DGU_FRONTEND_IMAGE
EOF

compose=(docker compose -p "$PROJECT_NAME" -f "$release_dir/docker-compose.yml" -f "$release_dir/docker-compose.prod.yml")
"${compose[@]}" config --quiet
"${compose[@]}" build api worker scheduler frontend
"${compose[@]}" run --rm -T api alembic upgrade head

deployment_started=0
rollback_images() {
  if [[ "$deployment_started" -ne 1 ]]; then
    return
  fi
  deployment_started=0
  echo "Deployment health check failed; restoring previous application images." >&2
  if [[ -n "$old_api" && -n "$old_worker" && -n "$old_scheduler" && -n "$old_frontend" ]]; then
    docker tag "$old_api" "dgu-rollback-api:$SHA"
    docker tag "$old_worker" "dgu-rollback-worker:$SHA"
    docker tag "$old_scheduler" "dgu-rollback-scheduler:$SHA"
    docker tag "$old_frontend" "dgu-rollback-frontend:$SHA"
    DGU_API_IMAGE="dgu-rollback-api:$SHA" \
    DGU_WORKER_IMAGE="dgu-rollback-worker:$SHA" \
    DGU_SCHEDULER_IMAGE="dgu-rollback-scheduler:$SHA" \
    DGU_FRONTEND_IMAGE="dgu-rollback-frontend:$SHA" \
    APP_VERSION_SHA="rollback-$SHA" \
      "${compose[@]}" up -d --no-build --pull never
  fi
}
trap rollback_images ERR

deployment_started=1
"${compose[@]}" up -d --no-build --remove-orphans

services=(postgres redis api worker scheduler frontend reverse-proxy)
deadline=$((SECONDS + 300))
while (( SECONDS < deadline )); do
  all_healthy=1
  for service in "${services[@]}"; do
    container=$("${compose[@]}" ps -q "$service")
    if [[ -z "$container" ]]; then
      all_healthy=0
      break
    fi
    state=$(docker inspect --format '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container")
    if [[ "$state" != "running|healthy" ]]; then
      all_healthy=0
      break
    fi
  done
  if [[ "$all_healthy" -eq 1 ]]; then
    break
  fi
  sleep 5
done
test "$all_healthy" -eq 1

curl --fail --silent --show-error --max-time 20 "$PUBLIC_URL/" >/dev/null
health=$(curl --fail --silent --show-error --max-time 20 "$PUBLIC_URL/api/health")
printf '%s' "$health" | grep -q "$SHA"
curl --fail --silent --show-error --max-time 20 "$PUBLIC_URL/api/ready" | grep -q 'ready'
migration=$("${compose[@]}" run --rm -T api alembic current | tail -n 1 | tr -d '\r\n')

record="$DATA_ROOT/storage/system/deployments/$SHA.json"
cat > "$record" <<EOF
{"commit_sha":"$SHA","deployed_at":"$DEPLOYED_AT","migration":"$migration","status":"healthy","production_mutate_performed":false}
EOF
chmod 600 "$record" "$release_dir/.deployment.env"

new_link="$CURRENT_LINK.new"
ln -sfn "$release_dir" "$new_link"
mv -Tf "$new_link" "$CURRENT_LINK"
deployment_started=0
trap - ERR
rm -f -- "$ARCHIVE" /tmp/deploy-release.sh
printf 'Deployment completed: %s\n' "$SHA"

#!/usr/bin/env sh
set -eu

umask 077

APP_DIR=${APP_DIR:-/opt/demand-gen-uploader}
BACKUP_ROOT=${BACKUP_ROOT:-/var/backups/demand-gen-uploader}
RETENTION_DAYS=${RETENTION_DAYS:-14}
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-demand-gen-uploader}
COMPOSE="docker compose -p $COMPOSE_PROJECT_NAME -f docker-compose.yml -f docker-compose.prod.yml"
STAMP=$(date -u +%Y%m%d-%H%M%S)
TMP_DIR="$BACKUP_ROOT/.tmp-$STAMP"
FINAL_DIR="$BACKUP_ROOT/$STAMP"

case "$BACKUP_ROOT" in
  /var/backups/demand-gen-uploader|/var/backups/demand-gen-uploader/*) ;;
  *) echo "Refusing unexpected BACKUP_ROOT: $BACKUP_ROOT" >&2; exit 2 ;;
esac

cd "$APP_DIR"
mkdir -p "$BACKUP_ROOT"
test ! -e "$TMP_DIR"
test ! -e "$FINAL_DIR"
mkdir "$TMP_DIR"

$COMPOSE exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "$TMP_DIR/postgres.dump"

storage_path=$(readlink -f "$APP_DIR/storage")
test -d "$storage_path"
tar -C "$(dirname "$storage_path")" -czf "$TMP_DIR/storage.tar.gz" "$(basename "$storage_path")"
cp .env "$TMP_DIR/environment.env"

$COMPOSE exec -T redis redis-cli SAVE >/dev/null
redis_container=$($COMPOSE ps -q redis)
docker cp "$redis_container:/data/dump.rdb" "$TMP_DIR/redis-dump.rdb" >/dev/null

$COMPOSE exec -T api alembic current > "$TMP_DIR/alembic-current.txt"
cp docker-compose.yml docker-compose.prod.yml infrastructure/caddy/Caddyfile "$TMP_DIR/"
(
  cd "$TMP_DIR"
  sha256sum \
    alembic-current.txt \
    Caddyfile \
    docker-compose.prod.yml \
    docker-compose.yml \
    environment.env \
    postgres.dump \
    redis-dump.rdb \
    storage.tar.gz \
    > SHA256SUMS
)
mv "$TMP_DIR" "$FINAL_DIR"

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
  -name '20??????-??????' -mtime "+$RETENTION_DAYS" -exec rm -rf -- {} +

printf 'Backup completed: %s\n' "$FINAL_DIR"

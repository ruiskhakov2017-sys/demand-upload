# Timeweb production deployment

The production site is available at `https://axyro.tech`. Caddy obtains and
renews certificates automatically. `https://www.axyro.tech` redirects to the
apex domain.

Before a domain is configured, the production override defaults to loopback
ports and can be checked through an SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 dguadmin@5.129.234.9
```

Then open `http://localhost:8080/` locally.

## Daily backups

The server timer runs `infrastructure/scripts/production-backup.sh`. Each
backup contains a PostgreSQL custom-format dump, storage archive, Redis RDB,
the root-only environment configuration, Alembic revision, Compose files, and
the active Caddy HTTPS configuration, and SHA-256 checksums. Backups are
stored in `/var/backups/demand-gen-uploader` and retained for 14 days.

Do not restore Redis automatically: inspect Celery queue and unacknowledged
tasks first. PostgreSQL and storage are authoritative for application data.

## Restore outline

1. Verify `SHA256SUMS` inside the selected backup.
2. Stop `api`, `worker`, and `scheduler`, leaving PostgreSQL and Redis up.
3. Restore `postgres.dump` with `pg_restore --clean --if-exists --no-owner`.
4. Restore `storage.tar.gz` into `/opt/demand-gen-uploader/storage`.
5. Run `alembic upgrade head` and start the application services.
6. Compare row counts, storage hashes, health endpoints, and the kill switch.
7. Restore Redis only after proving that no task can be replayed unsafely.

The local Windows deployment is the rollback target and must remain intact
until production acceptance is complete.

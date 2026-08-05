from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_production_backup_reads_migration_from_running_api() -> None:
    script = (PROJECT_ROOT / "infrastructure/scripts/production-backup.sh").read_text(
        encoding="utf-8"
    )

    assert '$COMPOSE exec -T api alembic current' in script
    assert '$COMPOSE run --rm -T api alembic current' not in script

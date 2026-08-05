from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_production_backup_reads_migration_from_running_api() -> None:
    script = (PROJECT_ROOT / "infrastructure/scripts/production-backup.sh").read_text(
        encoding="utf-8"
    )

    assert '$COMPOSE exec -T api alembic current' in script
    assert '$COMPOSE run --rm -T api alembic current' not in script


def test_deploy_runs_candidate_backup_code_against_active_release() -> None:
    script = (PROJECT_ROOT / "infrastructure/scripts/deploy-release.sh").read_text(
        encoding="utf-8"
    )

    assert 'APP_DIR="$previous_root" COMPOSE_PROJECT_NAME="$PROJECT_NAME"' in script
    assert '"$release_dir/infrastructure/scripts/production-backup.sh"' in script
    assert '"$previous_root/infrastructure/scripts/production-backup.sh"' not in script

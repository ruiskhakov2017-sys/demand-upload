"""add sync circuit breaker and operational saved views

Revision ID: 202607300010
Revises: 202607300009
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607300010"
down_revision: str | None = "202607300009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "google_connections",
        sa.Column(
            "sync_failure_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "google_connections",
        sa.Column(
            "sync_circuit_open_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_google_connections_sync_circuit_open_until"),
        "google_connections",
        ["sync_circuit_open_until"],
        unique=False,
    )

    op.execute(
        sa.text(
            r"""
            WITH presets(name, config, description) AS (
                VALUES
                (
                    'Аккаунты в работе',
                    '{"quickFilter":"working","period":"7d","grouping":"none","sortRules":[{"field":"name","direction":"asc"}]}'::jsonb,
                    'Основное ежедневное представление рабочих аккаунтов'
                ),
                (
                    'Индия в работе',
                    '{"quickFilter":"working","period":"7d","grouping":"mcc","sortRules":[{"field":"cost","direction":"desc"}]}'::jsonb,
                    'Все рабочие аккаунты Индии с группировкой по MCC'
                ),
                (
                    'Большой расход без депозитов',
                    '{"quickFilter":"working","period":"7d","costMin":"200","depositsZero"\:true,"sortRules":[{"field":"cost","direction":"desc"}]}'::jsonb,
                    'Рабочие аккаунты с расходом от 200 в валюте аккаунта и нулём депозитов'
                ),
                (
                    'Рабочие аккаунты без расхода',
                    '{"quickFilter":"working","period":"7d","activityStatus":"ENABLED_NO_SPEND","sortRules":[{"field":"last_sync","direction":"asc"}]}'::jsonb,
                    'Кампании включены, но расход за выбранный период отсутствует'
                ),
                (
                    'Заблокированные рабочие аккаунты',
                    '{"quickFilter":"working","activityStatus":"SUSPENDED","sortRules":[{"field":"name","direction":"asc"}]}'::jsonb,
                    'Рабочий статус сохраняется, блокировка отображается отдельно'
                ),
                (
                    'Аккаунты с отклонёнными объявлениями',
                    '{"quickFilter":"working","disapprovedAdsMin":"1","sortRules":[{"field":"disapproved_ads","direction":"desc"}]}'::jsonb,
                    'Аккаунты, где Google вернул отклонённые объявления'
                ),
                (
                    'Данные давно не обновлялись',
                    '{"quickFilter":"all","activityStatus":"STALE","sortRules":[{"field":"last_sync","direction":"asc"}]}'::jsonb,
                    'Аккаунты с устаревшими данными синхронизации'
                )
            ),
            prepared AS (
                SELECT
                    u.id AS owner_user_id,
                    presets.name,
                    CASE
                        WHEN presets.name = 'Индия в работе'
                        THEN presets.config || jsonb_build_object(
                            'geoId',
                            COALESCE(
                                (SELECT id::text FROM geo_definitions WHERE iso_code = 'IN' LIMIT 1),
                                ''
                            )
                        )
                        ELSE presets.config
                    END AS config,
                    presets.description,
                    (
                        presets.name = 'Аккаунты в работе'
                        AND NOT EXISTS (
                            SELECT 1
                            FROM control_center_saved_views existing
                            WHERE existing.owner_user_id = u.id
                              AND existing.entity_level = 'ACCOUNT'
                              AND existing.is_default IS TRUE
                        )
                    ) AS is_default
                FROM users u
                CROSS JOIN presets
                WHERE u.role = 'ADMIN' AND u.is_active IS TRUE
            )
            INSERT INTO control_center_saved_views (
                id,
                owner_user_id,
                entity_level,
                name,
                config,
                is_default,
                is_shared,
                description
            )
            SELECT
                gen_random_uuid(),
                owner_user_id,
                'ACCOUNT',
                name,
                config,
                is_default,
                TRUE,
                description
            FROM prepared
            ON CONFLICT (owner_user_id, entity_level, name) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # Preset views are ordinary user-editable data after creation and are retained.
    op.drop_index(
        op.f("ix_google_connections_sync_circuit_open_until"),
        table_name="google_connections",
    )
    op.drop_column("google_connections", "sync_circuit_open_until")
    op.drop_column("google_connections", "sync_failure_count")

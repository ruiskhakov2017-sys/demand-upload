from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.db.models import CustomerAccount, GoogleConnection, User
from app.google_ads.test_acceptance import (
    run_control_center_acceptance,
    run_demand_gen_acceptance,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GOOGLE_TEST_INTEGRATION") != "1",
    reason="Set RUN_GOOGLE_TEST_INTEGRATION=1 for the isolated Google Test hierarchy",
)


def test_real_google_test_hierarchy_and_demand_gen() -> None:
    with SessionLocal() as db:
        connection = db.scalar(
            select(GoogleConnection).where(
                GoogleConnection.name == "google-test"
            )
        )
        assert connection is not None
        assert connection.connection_mode == "GOOGLE_TEST"
        assert connection.login_customer_id == "3831073849"
        assert connection.status == "VERIFIED"

        accounts = list(
            db.scalars(
                select(CustomerAccount).where(
                    CustomerAccount.connection_id == connection.id,
                    CustomerAccount.customer_id.in_(
                        ["1833869760", "8047280949"]
                    ),
                )
            ).all()
        )
        assert {item.customer_id for item in accounts} == {
            "1833869760",
            "8047280949",
        }
        assert all(item.is_test_account for item in accounts)
        assert all(not item.can_manage_clients for item in accounts)
        actor = db.scalar(select(User).where(User.username == "admin"))
        assert actor is not None

        demand_gen = run_demand_gen_acceptance(
            db,
            connection,
            "1833869760",
            actor.id,
        )
        assert demand_gen.status == "SUCCEEDED"
        assert demand_gen.readback["verified"]["campaign_paused"] is True
        assert demand_gen.readback["verified"]["budget_present"] is True
        assert demand_gen.readback["verified"]["ad_groups_present"] is True
        assert demand_gen.readback["verified"]["ads_present"] is True
        assert demand_gen.readback["verified"]["assets_present"] is True
        assert demand_gen.readback["verified"]["audiences_present"] is True
        assert demand_gen.request_ids

        control = run_control_center_acceptance(
            db,
            connection,
            "8047280949",
            actor.id,
        )
        assert control.status == "SUCCEEDED"
        steps = control.readback["control_center_steps"]
        assert [item["action"] for item in steps] == [
            "ENABLED",
            "PAUSED",
            "SET_BUDGET",
        ]
        assert all(item["verified"] for item in steps)
        assert control.request_ids

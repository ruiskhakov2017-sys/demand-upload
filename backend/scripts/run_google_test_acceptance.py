from __future__ import annotations

import json

from sqlalchemy import select

from app.core.database import SessionLocal
from app.db.models import GoogleConnection, User
from app.google_ads.test_acceptance import (
    run_control_center_acceptance,
    run_demand_gen_acceptance,
)


def main() -> None:
    with SessionLocal() as db:
        connection = db.scalar(
            select(GoogleConnection).where(
                GoogleConnection.name == "google-test"
            )
        )
        actor = db.scalar(select(User).where(User.username == "admin"))
        if connection is None or actor is None:
            raise SystemExit("google-test connection or admin user is missing")
        if connection.status != "VERIFIED":
            raise SystemExit(
                "google-test OAuth and hierarchy must be VERIFIED first"
            )
        demand_gen = run_demand_gen_acceptance(
            db, connection, "1833869760", actor.id
        )
        control = run_control_center_acceptance(
            db, connection, "8047280949", actor.id
        )
        print(
            json.dumps(
                {
                    "demand_gen": {
                        "status": demand_gen.status,
                        "resource_names": demand_gen.resource_names,
                        "request_ids": demand_gen.request_ids,
                        "readback": demand_gen.readback,
                    },
                    "control_center": {
                        "status": control.status,
                        "resource_names": control.resource_names,
                        "request_ids": control.request_ids,
                        "readback": control.readback,
                    },
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()

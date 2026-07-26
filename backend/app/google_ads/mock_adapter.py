from __future__ import annotations

import hashlib

from app.google_ads.interface import PlanExecutionResult, YouTubeUploadResult


class MockGoogleAdsAdapter:
    """Deterministic offline adapter. It never contacts Google and is always labeled SIMULATION."""

    def validate_plan(self, snapshot: dict) -> PlanExecutionResult:
        campaigns = snapshot.get("campaigns") or []
        instance_results = [
            {
                "campaign_instance_id": campaign.get("campaign_instance_id"),
                "customer_id": campaign.get("customer_id"),
                "campaign_name": campaign.get("campaign_name"),
                "ok": True,
                "errors": [],
                "warnings": [],
                "request_ids": [],
                "resource_names": [],
            }
            for campaign in campaigns
        ]
        return PlanExecutionResult(
            ok=True,
            mode="SIMULATION",
            errors=[],
            warnings=[
                {
                    "code": "NO_GOOGLE_REQUEST",
                    "message": "Симуляция: Google Ads API не вызывался, request ID отсутствует",
                }
            ],
            request_ids=[],
            resource_names=[],
            details={
                "validate_only": True,
                "campaigns_checked": len(campaigns),
                "google_contacted": False,
                "instances": instance_results,
            },
        )

    def deploy_plan(self, snapshot: dict) -> PlanExecutionResult:
        resources: list[str] = []
        instance_results: list[dict] = []
        for index, campaign in enumerate(snapshot.get("campaigns") or []):
            customer_id = campaign.get("customer_id") or "simulation"
            digest = hashlib.sha256(
                f"{snapshot.get('upload_id')}:{index}:{campaign.get('campaign_name')}".encode()
            ).hexdigest()[:12]
            resource_name = f"customers/{customer_id}/campaigns/sim-{digest}"
            resources.append(resource_name)
            instance_results.append(
                {
                    "campaign_instance_id": campaign.get("campaign_instance_id"),
                    "customer_id": customer_id,
                    "campaign_name": campaign.get("campaign_name"),
                    "ok": True,
                    "errors": [],
                    "warnings": [],
                    "request_ids": [],
                    "resource_names": [resource_name],
                }
            )
        return PlanExecutionResult(
            ok=True,
            mode="SIMULATION",
            errors=[],
            warnings=[
                {
                    "code": "NO_GOOGLE_REQUEST",
                    "message": "Созданы только локальные результаты; в Google Ads ничего не отправлено",
                }
            ],
            request_ids=[],
            resource_names=resources,
            details={
                "validate_only": False,
                "google_contacted": False,
                "campaign_status": "PAUSED",
                "instances": instance_results,
            },
        )

    def change_campaign_status(self, customer_id: str, campaigns: list[dict], status: str) -> PlanExecutionResult:
        rows = [
            {
                "campaign_instance_id": item.get("campaign_instance_id"),
                "customer_id": customer_id,
                "ok": True,
                "errors": [],
                "warnings": [],
                "request_ids": [],
                "resource_names": [item["resource_name"]],
                "status": status,
            }
            for item in campaigns
        ]
        return PlanExecutionResult(
            ok=True,
            mode="SIMULATION",
            errors=[],
            warnings=[{"code": "NO_GOOGLE_REQUEST", "message": "Статус изменён только в тестовом режиме"}],
            request_ids=[],
            resource_names=[item["resource_name"] for item in campaigns],
            details={"google_contacted": False, "status": status, "instances": rows},
        )

    def fetch_campaign_performance(self, customer_id: str, resource_names: list[str]) -> list[dict]:
        rows = []
        for index, resource_name in enumerate(resource_names):
            sequence = index + 1
            metrics = {
                "impressions": 1000 + sequence * 300,
                "clicks": 25 + sequence * 11,
                "cost_micros": (110 + sequence * 18) * 1_000_000,
                "conversions": float(max(0, sequence - 1)),
                "conversion_value": float(max(0, sequence - 1) * 32),
            }
            rows.append({"customer_id": customer_id, "resource_name": resource_name, "metrics": metrics})
        return rows

    def fetch_account_catalog(self, customer_id: str) -> dict:
        return {
            "customer_id": customer_id,
            "mode": "SIMULATION",
            "google_contacted": False,
            "conversion_actions": [],
            "audiences": [],
            "user_lists": [],
            "assets": [],
        }

    def read_campaign(self, customer_id: str, campaign_resource_name: str) -> dict:
        return {
            "customer_id": customer_id,
            "campaign_resource_name": campaign_resource_name,
            "mode": "SIMULATION",
            "google_contacted": False,
            "template": {
                "campaign": {"ad_type": "IMAGE", "ad_group_name": "Основная группа"},
                "bidding": {"strategy": "TARGET_CPA", "target_cpa": 10},
                "targeting": {"location_ids": ["2840"], "language_ids": ["1000"]},
                "url": {"final_url": "https://example.com"},
                "texts": {
                    "business_name": "Demo",
                    "headlines": ["Demo headline"],
                    "descriptions": ["Demo description"],
                },
            },
        }

    def start_youtube_video_upload(
        self, customer_id: str, file_path: str, title: str, description: str
    ) -> YouTubeUploadResult:
        digest = hashlib.sha256(f"{customer_id}:{file_path}:{title}".encode()).hexdigest()
        video_id = digest[:11]
        return YouTubeUploadResult(
            state="PROCESSED",
            resource_name=f"customers/{customer_id}/youTubeVideoUploads/sim-{digest[:16]}",
            video_id=video_id,
            message="Симуляция загрузки завершена; Google и YouTube не вызывались",
        )

    def get_youtube_video_upload(self, customer_id: str, resource_name: str) -> YouTubeUploadResult:
        digest = hashlib.sha256(resource_name.encode()).hexdigest()
        return YouTubeUploadResult(
            state="PROCESSED",
            resource_name=resource_name,
            video_id=digest[:11],
            message="Симуляция обработки завершена",
        )

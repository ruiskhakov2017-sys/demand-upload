from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.google_ads.client_factory import google_ads_client, normalize_customer_id
from app.google_ads.errors import GoogleAdsAdapterError
from app.google_ads.interface import (
    AdapterCheckResult,
    CustomerAccountInfo,
    GoogleAdsConnectionConfig,
    PlanExecutionResult,
    YouTubeUploadResult,
)

MCC_CUSTOMER_QUERY = """
    SELECT
      customer.id,
      customer.descriptive_name,
      customer.manager,
      customer.test_account,
      customer.currency_code,
      customer.time_zone
    FROM customer
    LIMIT 1
"""


class GoogleAdsV242Adapter:
    def __init__(self, config: GoogleAdsConnectionConfig) -> None:
        self.config = config

    def test_connection(self) -> AdapterCheckResult:
        customer_id = normalize_customer_id(self.config.login_customer_id)
        try:
            with google_ads_client(self.config) as client:
                service = client.get_service("GoogleAdsService")
                response = service.search(customer_id=customer_id, query=MCC_CUSTOMER_QUERY)
                row = next(iter(response), None)
        except Exception as exc:
            return _connection_check_failure(exc, customer_id, self.config.api_version)

        if row is None:
            return AdapterCheckResult(
                ok=False,
                status="ERROR",
                message=f"Google Ads не вернул данные MCC {customer_id} на безопасный запрос чтения.",
                api_version=self.config.api_version,
            )

        customer = row.customer
        if normalize_customer_id(str(customer.id)) != customer_id:
            return AdapterCheckResult(
                ok=False,
                status="ERROR",
                message=f"Google Ads вернул другой Customer ID: {customer.id} вместо {customer_id}.",
                api_version=self.config.api_version,
            )
        if not bool(customer.manager):
            return AdapterCheckResult(
                ok=False,
                status="ERROR",
                message=f"Аккаунт {customer_id} доступен, но Google Ads не считает его управляющим MCC.",
                api_version=self.config.api_version,
            )

        name = customer.descriptive_name or customer_id
        return AdapterCheckResult(
            ok=True,
            status="VERIFIED",
            message=(
                f"MCC подтверждён: {name} ({customer_id}), "
                f"{customer.currency_code}, {customer.time_zone}."
            ),
            api_version=self.config.api_version,
        )

    def list_customer_accounts(self) -> list[CustomerAccountInfo]:
        manager_customer_id = normalize_customer_id(self.config.login_customer_id)
        query = """
            SELECT
              customer_client.client_customer,
              customer_client.descriptive_name,
              customer_client.currency_code,
              customer_client.time_zone,
              customer_client.manager,
              customer_client.test_account,
              customer_client.hidden,
              customer_client.status
            FROM customer_client
            WHERE customer_client.level <= 1
        """
        accounts: list[CustomerAccountInfo] = []
        try:
            with google_ads_client(self.config) as client:
                google_ads_service = client.get_service("GoogleAdsService")
                stream = google_ads_service.search_stream(
                    customer_id=manager_customer_id,
                    query=query,
                )
                for batch in stream:
                    for row in batch.results:
                        resource_name = row.customer_client.client_customer
                        customer_id = resource_name.rsplit("/", 1)[-1]
                        if customer_id == manager_customer_id:
                            continue
                        accounts.append(
                            CustomerAccountInfo(
                                customer_id=customer_id,
                                manager_customer_id=manager_customer_id,
                                descriptive_name=row.customer_client.descriptive_name or None,
                                currency_code=row.customer_client.currency_code or None,
                                time_zone=row.customer_client.time_zone or None,
                                can_manage_clients=bool(row.customer_client.manager),
                                is_test_account=bool(row.customer_client.test_account),
                                is_hidden=bool(row.customer_client.hidden),
                                status=row.customer_client.status.name
                                if hasattr(row.customer_client.status, "name")
                                else str(row.customer_client.status),
                            )
                        )
        except Exception as exc:
            message, _ = _google_ads_failure_message(
                exc,
                manager_customer_id,
                f"Синхронизация аккаунтов MCC {manager_customer_id} не выполнена",
            )
            raise GoogleAdsAdapterError(message) from exc
        return accounts

    def fetch_moderation(self, customer_ids: list[str]) -> list[dict]:
        query = """
            SELECT ad_group_ad.resource_name,
                   ad_group_ad.policy_summary.approval_status,
                   ad_group_ad.policy_summary.policy_topic_entries
            FROM ad_group_ad
            WHERE campaign.advertising_channel_type = DEMAND_GEN
        """
        result: list[dict] = []
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for customer_id in customer_ids:
                for batch in service.search_stream(customer_id=customer_id, query=query):
                    for row in batch.results:
                        summary = row.ad_group_ad.policy_summary
                        result.append(
                            {
                                "customer_id": customer_id,
                                "resource_name": row.ad_group_ad.resource_name,
                                "approval_status": getattr(summary.approval_status, "name", None)
                                or str(summary.approval_status),
                                "policy_topics": [
                                    {
                                        "topic": entry.topic,
                                        "type": getattr(entry.type_, "name", None) or str(entry.type_),
                                    }
                                    for entry in summary.policy_topic_entries
                                ],
                            }
                        )
        return result

    def fetch_statistics(self, customer_ids: list[str]) -> list[dict]:
        query = """
            SELECT segments.date,
                   metrics.impressions,
                   metrics.clicks,
                   metrics.cost_micros,
                   metrics.conversions
            FROM campaign
            WHERE campaign.advertising_channel_type = DEMAND_GEN
              AND segments.date DURING LAST_30_DAYS
        """
        totals: dict[tuple[str, str], dict] = {}
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for customer_id in customer_ids:
                for batch in service.search_stream(customer_id=customer_id, query=query):
                    for row in batch.results:
                        key = (customer_id, str(row.segments.date))
                        item = totals.setdefault(
                            key,
                            {"impressions": 0, "clicks": 0, "cost_micros": 0, "conversions": 0.0},
                        )
                        item["impressions"] += int(row.metrics.impressions)
                        item["clicks"] += int(row.metrics.clicks)
                        item["cost_micros"] += int(row.metrics.cost_micros)
                        item["conversions"] += float(row.metrics.conversions)
        return [
            {"customer_id": customer_id, "snapshot_date": snapshot_date, "metrics": metrics}
            for (customer_id, snapshot_date), metrics in totals.items()
        ]

    def validate_plan(self, snapshot: dict) -> PlanExecutionResult:
        return self._execute_plan(snapshot, validate_only=True)

    def deploy_plan(self, snapshot: dict) -> PlanExecutionResult:
        return self._execute_plan(snapshot, validate_only=False)

    def change_campaign_status(self, customer_id: str, campaigns: list[dict], status: str) -> PlanExecutionResult:
        requested_status = status.upper()
        if requested_status not in {"ENABLED", "PAUSED"}:
            raise ValueError("Google Ads поддерживает только ENABLED или PAUSED для этого действия")
        errors: list[dict] = []
        request_ids: list[str] = []
        rows: list[dict] = []
        with google_ads_client(self.config) as client:
            request = client.get_type("MutateGoogleAdsRequest")
            request.customer_id = customer_id
            request.partial_failure = False
            for item in campaigns:
                operation = client.get_type("MutateOperation")
                campaign = operation.campaign_operation.update
                campaign.resource_name = item["resource_name"]
                campaign.status = getattr(client.enums.CampaignStatusEnum, requested_status)
                operation.campaign_operation.update_mask.paths.append("status")
                request.mutate_operations.append(operation)
            try:
                client.get_service("GoogleAdsService").mutate(request=request)
                rows = [
                    {
                        "campaign_instance_id": item.get("campaign_instance_id"),
                        "customer_id": customer_id,
                        "ok": True,
                        "errors": [],
                        "warnings": [],
                        "request_ids": [],
                        "resource_names": [item["resource_name"]],
                        "status": requested_status,
                    }
                    for item in campaigns
                ]
            except Exception as exc:
                issues, request_id = _google_exception(exc, customer_id, None)
                errors.extend(issues)
                if request_id:
                    request_ids.append(request_id)
                rows = [
                    {
                        "campaign_instance_id": item.get("campaign_instance_id"),
                        "customer_id": customer_id,
                        "ok": False,
                        "errors": issues,
                        "warnings": [],
                        "request_ids": [request_id] if request_id else [],
                        "resource_names": [item["resource_name"]],
                        "status": requested_status,
                    }
                    for item in campaigns
                ]
        return PlanExecutionResult(
            ok=not errors,
            mode="LIVE",
            errors=errors,
            warnings=[],
            request_ids=request_ids,
            resource_names=[item["resource_name"] for item in campaigns],
            details={"google_contacted": True, "status": requested_status, "instances": rows},
        )

    def fetch_campaign_performance(self, customer_id: str, resource_names: list[str]) -> list[dict]:
        if not resource_names:
            return []
        values = ", ".join(f"'{_escape_gaql(item)}'" for item in resource_names)
        query = f"""
            SELECT campaign.resource_name,
                   campaign.name,
                   campaign.status,
                   metrics.impressions,
                   metrics.clicks,
                   metrics.cost_micros,
                   metrics.conversions,
                   metrics.conversions_value
            FROM campaign
            WHERE campaign.resource_name IN ({values})
              AND segments.date DURING LAST_30_DAYS
        """
        rows: list[dict] = []
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for batch in service.search_stream(customer_id=customer_id, query=query):
                for row in batch.results:
                    rows.append(
                        {
                            "customer_id": customer_id,
                            "resource_name": str(row.campaign.resource_name),
                            "campaign_name": row.campaign.name,
                            "status": _enum_name(row.campaign.status),
                            "metrics": {
                                "impressions": int(row.metrics.impressions),
                                "clicks": int(row.metrics.clicks),
                                "cost_micros": int(row.metrics.cost_micros),
                                "conversions": float(row.metrics.conversions),
                                "conversion_value": float(row.metrics.conversions_value),
                            },
                        }
                    )
        return rows

    def fetch_account_catalog(self, customer_id: str) -> dict:
        queries = {
            "conversion_actions": """
                SELECT conversion_action.resource_name, conversion_action.name,
                       conversion_action.category, conversion_action.status
                FROM conversion_action
                WHERE conversion_action.status != REMOVED
                LIMIT 10000
            """,
            "audiences": """
                SELECT audience.resource_name, audience.name, audience.description
                FROM audience
                LIMIT 10000
            """,
            "user_lists": """
                SELECT user_list.resource_name, user_list.name, user_list.type,
                       user_list.size_for_display
                FROM user_list
                LIMIT 10000
            """,
            "assets": """
                SELECT asset.resource_name, asset.name, asset.type
                FROM asset
                LIMIT 10000
            """,
        }
        result: dict[str, list[dict] | str | bool] = {
            "customer_id": customer_id,
            "mode": "LIVE",
            "google_contacted": True,
        }
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            result["conversion_actions"] = [
                {
                    "resource_name": str(row.conversion_action.resource_name),
                    "name": row.conversion_action.name,
                    "category": _enum_name(row.conversion_action.category),
                    "status": _enum_name(row.conversion_action.status),
                }
                for row in service.search(customer_id=customer_id, query=queries["conversion_actions"])
            ]
            result["audiences"] = [
                {
                    "resource_name": str(row.audience.resource_name),
                    "name": row.audience.name,
                    "description": row.audience.description,
                }
                for row in service.search(customer_id=customer_id, query=queries["audiences"])
            ]
            result["user_lists"] = [
                {
                    "resource_name": str(row.user_list.resource_name),
                    "name": row.user_list.name,
                    "type": _enum_name(row.user_list.type_),
                    "size_for_display": int(row.user_list.size_for_display),
                }
                for row in service.search(customer_id=customer_id, query=queries["user_lists"])
            ]
            result["assets"] = [
                {
                    "resource_name": str(row.asset.resource_name),
                    "name": row.asset.name,
                    "type": _enum_name(row.asset.type_),
                }
                for row in service.search(customer_id=customer_id, query=queries["assets"])
            ]
        return result

    def read_campaign(self, customer_id: str, campaign_resource_name: str) -> dict:
        query = f"""
            SELECT campaign.resource_name, campaign.name, campaign.status,
                   campaign.campaign_budget, campaign.bidding_strategy_type,
                   campaign.target_cpa.target_cpa_micros,
                   campaign.target_roas.target_roas,
                   campaign.start_date_time, campaign.end_date_time,
                   campaign.tracking_url_template, campaign.final_url_suffix
            FROM campaign
            WHERE campaign.resource_name = '{_escape_gaql(campaign_resource_name)}'
              AND campaign.advertising_channel_type = DEMAND_GEN
            LIMIT 1
        """
        with google_ads_client(self.config) as client:
            row = next(iter(client.get_service("GoogleAdsService").search(customer_id=customer_id, query=query)), None)
        if not row:
            raise ValueError("Кампания Demand Gen не найдена в выбранном аккаунте")
        strategy = _enum_name(row.campaign.bidding_strategy_type)
        template = {
            "campaign": {
                "source_campaign_resource": str(row.campaign.resource_name),
                "ad_group_name": "Основная группа",
                "ad_type": "IMAGE",
                "start_date_time": row.campaign.start_date_time or None,
                "end_date_time": row.campaign.end_date_time or None,
            },
            "bidding": {
                "strategy": strategy,
                "target_cpa_micros": int(row.campaign.target_cpa.target_cpa_micros or 0),
                "target_roas": float(row.campaign.target_roas.target_roas or 0),
            },
            "url": {
                "tracking_template": row.campaign.tracking_url_template or None,
                "final_url_suffix": row.campaign.final_url_suffix or None,
            },
            "targeting": {},
            "texts": {},
            "ads": {},
        }
        return {
            "customer_id": customer_id,
            "campaign_resource_name": campaign_resource_name,
            "mode": "LIVE",
            "google_contacted": True,
            "source_campaign_name": row.campaign.name,
            "template": template,
        }

    def _execute_plan(self, snapshot: dict, validate_only: bool) -> PlanExecutionResult:
        errors: list[dict] = []
        warnings: list[dict] = []
        request_ids: list[str] = []
        resources: list[str] = []
        instance_results: list[dict] = []
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for campaign in snapshot.get("campaigns") or []:
                customer_id = str(campaign["customer_id"])
                instance_result = {
                    "campaign_instance_id": campaign.get("campaign_instance_id"),
                    "customer_id": customer_id,
                    "campaign_name": campaign.get("campaign_name"),
                    "ok": True,
                    "errors": [],
                    "warnings": [],
                    "request_ids": [],
                    "resource_names": [],
                }
                if not validate_only:
                    existing = self._find_existing_campaign(service, customer_id, campaign["google_campaign_name"])
                    if existing:
                        resources.append(existing)
                        warning = {
                            "code": "IDEMPOTENT_REUSE",
                            "message": f"Кампания уже существует: {campaign['google_campaign_name']}",
                        }
                        warnings.append(warning)
                        instance_result["warnings"].append(warning)
                        instance_result["resource_names"].append(existing)
                        instance_results.append(instance_result)
                        continue
                try:
                    operations = self._build_operations(
                        client,
                        customer_id,
                        campaign,
                        snapshot.get("media") or [],
                        service=service,
                    )
                    request = client.get_type("MutateGoogleAdsRequest")
                    request.customer_id = customer_id
                    request.mutate_operations.extend(operations)
                    request.partial_failure = False
                    request.validate_only = validate_only
                    response = service.mutate(request=request)
                    if not validate_only:
                        created_resources = _resource_names(response)
                        resources.extend(created_resources)
                        instance_result["resource_names"].extend(created_resources)
                except Exception as exc:
                    issue, request_id = _google_exception(exc, customer_id, campaign.get("campaign_name"))
                    errors.extend(issue)
                    instance_result["ok"] = False
                    instance_result["errors"].extend(issue)
                    if request_id:
                        request_ids.append(request_id)
                        instance_result["request_ids"].append(request_id)
                instance_results.append(instance_result)

        return PlanExecutionResult(
            ok=not errors,
            mode="LIVE",
            errors=errors,
            warnings=warnings,
            request_ids=request_ids,
            resource_names=resources,
            details={
                "validate_only": validate_only,
                "google_contacted": True,
                "campaign_status": "PAUSED",
                "atomic_scope": "campaign",
                "instances": instance_results,
            },
        )

    def _find_existing_campaign(self, service: Any, customer_id: str, campaign_name: str) -> str | None:
        escaped = campaign_name.replace("\\", "\\\\").replace("'", "\\'")
        query = f"""
            SELECT campaign.resource_name
            FROM campaign
            WHERE campaign.name = '{escaped}'
              AND campaign.advertising_channel_type = DEMAND_GEN
            LIMIT 1
        """
        response = service.search(customer_id=customer_id, query=query)
        for row in response:
            return str(row.campaign.resource_name)
        return None

    def _find_existing_asset(self, service: Any, customer_id: str, asset_name: str) -> str | None:
        query = f"""
            SELECT asset.resource_name
            FROM asset
            WHERE asset.name = '{_escape_gaql(asset_name)}'
            LIMIT 1
        """
        for row in service.search(customer_id=customer_id, query=query):
            return str(row.asset.resource_name)
        return None

    def _build_operations(
        self,
        client: Any,
        customer_id: str,
        campaign: dict,
        media: list[dict],
        service: Any | None = None,
    ) -> list[Any]:
        operations: list[Any] = []
        budget_name = client.get_service("CampaignBudgetService").campaign_budget_path(customer_id, -1)
        campaign_name = client.get_service("CampaignService").campaign_path(customer_id, -2)
        ad_group_name = client.get_service("AdGroupService").ad_group_path(customer_id, -3)

        budget_op = client.get_type("MutateOperation")
        budget = budget_op.campaign_budget_operation.create
        budget.resource_name = budget_name
        budget.name = f"{campaign['google_campaign_name']} budget"
        if str(campaign.get("budget_type") or "DAILY").upper() == "TOTAL":
            budget.total_amount_micros = int(campaign["daily_budget_micros"])
            budget.period = client.enums.BudgetPeriodEnum.CUSTOM_PERIOD
        else:
            budget.amount_micros = int(campaign["daily_budget_micros"])
        budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget.explicitly_shared = False
        operations.append(budget_op)

        campaign_op = client.get_type("MutateOperation")
        created_campaign = campaign_op.campaign_operation.create
        created_campaign.resource_name = campaign_name
        created_campaign.name = campaign["google_campaign_name"]
        created_campaign.status = client.enums.CampaignStatusEnum.PAUSED
        created_campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.DEMAND_GEN
        created_campaign.campaign_budget = budget_name
        _set_bidding(client, created_campaign, campaign)
        if campaign.get("start_date_time"):
            created_campaign.start_date_time = _google_date_time(campaign["start_date_time"])
        if campaign.get("end_date_time"):
            created_campaign.end_date_time = _google_date_time(campaign["end_date_time"])
        if campaign.get("tracking_template"):
            created_campaign.tracking_url_template = campaign["tracking_template"]
        if campaign.get("final_url_suffix"):
            created_campaign.final_url_suffix = campaign["final_url_suffix"]
        _append_custom_parameters(
            client,
            created_campaign.url_custom_parameters,
            campaign.get("custom_parameters") or [],
        )
        for resource_name in campaign.get("conversion_action_resource_names") or []:
            created_campaign.selective_optimization.conversion_actions.append(resource_name)
        created_campaign.contains_eu_political_advertising = (
            client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
        )
        operations.append(campaign_op)

        ad_group_op = client.get_type("MutateOperation")
        ad_group = ad_group_op.ad_group_operation.create
        ad_group.resource_name = ad_group_name
        ad_group.name = str(campaign["ad_group_name"])[:255]
        ad_group.campaign = campaign_name
        ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
        ad_group.optimized_targeting_enabled = bool(campaign.get("optimized_targeting", True))
        _configure_channel_controls(client, ad_group, campaign.get("channel_controls") or {})
        operations.append(ad_group_op)

        for location_id in campaign.get("location_ids") or []:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    "location.geo_target_constant",
                    f"geoTargetConstants/{location_id}",
                )
            )
        for location_id in campaign.get("excluded_location_ids") or []:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    "location.geo_target_constant",
                    f"geoTargetConstants/{location_id}",
                    negative=True,
                )
            )
        for language_id in campaign.get("language_ids") or []:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    "language.language_constant",
                    f"languageConstants/{language_id}",
                )
            )
        for resource_name in campaign.get("audience_resource_names") or []:
            operations.append(_criterion_operation(client, ad_group_name, "audience.audience", resource_name))
        for resource_name in campaign.get("user_list_resource_names") or []:
            operations.append(_criterion_operation(client, ad_group_name, "user_list.user_list", resource_name))
        for resource_name in campaign.get("custom_audience_resource_names") or []:
            operations.append(
                _criterion_operation(client, ad_group_name, "custom_audience.custom_audience", resource_name)
            )
        for resource_name in campaign.get("user_interest_resource_names") or []:
            operations.append(
                _criterion_operation(client, ad_group_name, "user_interest.user_interest_category", resource_name)
            )
        for life_event_id in campaign.get("life_event_ids") or []:
            operations.append(_criterion_operation(client, ad_group_name, "life_event.life_event_id", life_event_id))
        _append_demographic_operations(client, operations, ad_group_name, campaign.get("demographics") or {})
        _append_schedule_operations(client, operations, campaign_name, campaign.get("schedule") or [])

        selected_ids = set(campaign.get("media_ids") or [])
        selected_media = [item for item in media if item.get("id") in selected_ids]
        next_temp_id = -10
        image_assets: list[tuple[str, dict]] = []
        for item in selected_media:
            if item.get("kind") != "IMAGE" or not item.get("storage_key"):
                continue
            _customer_scope, sha256 = asset_cache_key(customer_id, str(item["sha256"]))
            stable_name = f"DGU image {sha256}"[:255]
            asset_name = self._find_existing_asset(service, customer_id, stable_name) if service else None
            if not asset_name:
                asset_name = client.get_service("AssetService").asset_path(customer_id, next_temp_id)
                next_temp_id -= 1
                asset_op = client.get_type("MutateOperation")
                asset = asset_op.asset_operation.create
                asset.resource_name = asset_name
                asset.name = stable_name
                asset.type_ = client.enums.AssetTypeEnum.IMAGE
                asset.image_asset.data = (settings.storage_root / item["storage_key"]).read_bytes()
                operations.append(asset_op)
            image_assets.append((asset_name, item))

        youtube_id = str(campaign.get("youtube_video_id") or "")
        if not youtube_id:
            youtube_id = next(
                (str(item.get("youtube_video_id")) for item in selected_media if item.get("youtube_video_id")), ""
            )
        video_asset_name: str | None = None
        if youtube_id:
            stable_name = f"DGU YouTube {youtube_id}"
            video_asset_name = self._find_existing_asset(service, customer_id, stable_name) if service else None
            if not video_asset_name:
                video_asset_name = client.get_service("AssetService").asset_path(customer_id, next_temp_id)
                next_temp_id -= 1
                asset_op = client.get_type("MutateOperation")
                asset = asset_op.asset_operation.create
                asset.resource_name = video_asset_name
                asset.name = stable_name
                asset.type_ = client.enums.AssetTypeEnum.YOUTUBE_VIDEO
                asset.youtube_video_asset.youtube_video_id = youtube_id
                operations.append(asset_op)

        ad_op = client.get_type("MutateOperation")
        ad_group_ad = ad_op.ad_group_ad_operation.create
        ad_group_ad.ad_group = ad_group_name
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
        ad = ad_group_ad.ad
        ad.name = f"{campaign['google_campaign_name']} ad"[:255]
        ad.final_urls.append(campaign["final_url"])
        if campaign.get("mobile_final_url"):
            ad.final_mobile_urls.append(campaign["mobile_final_url"])
        if campaign.get("tracking_template"):
            ad.tracking_url_template = campaign["tracking_template"]
        if campaign.get("final_url_suffix"):
            ad.final_url_suffix = campaign["final_url_suffix"]
        _append_custom_parameters(client, ad.url_custom_parameters, campaign.get("custom_parameters") or [])
        if campaign.get("ad_type") == "VIDEO":
            info = ad.demand_gen_video_responsive_ad
            info.business_name.text = campaign["business_name"]
            if video_asset_name:
                video_link = client.get_type("AdVideoAsset")
                video_link.asset = video_asset_name
                info.videos.append(video_link)
            square_assets = [item for item in image_assets if _image_role(item[1]) == "SQUARE"]
            companion_assets = [item for item in image_assets if _image_role(item[1]) == "LANDSCAPE"]
            for asset_name, _item in (square_assets or image_assets)[:5]:
                image_link = client.get_type("AdImageAsset")
                image_link.asset = asset_name
                info.logo_images.append(image_link)
            for asset_name, _item in companion_assets[:1]:
                image_link = client.get_type("AdImageAsset")
                image_link.asset = asset_name
                info.companion_banners.append(image_link)
            _append_text_assets(client, info.headlines, campaign.get("headlines") or [])
            _append_text_assets(client, info.long_headlines, [campaign["long_headline"]])
            _append_text_assets(client, info.descriptions, campaign.get("descriptions") or [])
            cta_asset_name = client.get_service("AssetService").asset_path(customer_id, next_temp_id)
            cta_op = client.get_type("MutateOperation")
            cta_asset = cta_op.asset_operation.create
            cta_asset.resource_name = cta_asset_name
            cta_asset.name = f"DGU CTA {campaign.get('call_to_action') or 'LEARN_MORE'}"
            cta_asset.type_ = client.enums.AssetTypeEnum.CALL_TO_ACTION
            cta_asset.call_to_action_asset.call_to_action = getattr(
                client.enums.CallToActionTypeEnum,
                str(campaign.get("call_to_action") or "LEARN_MORE").upper(),
            )
            operations.append(cta_op)
            cta_link = client.get_type("AdCallToActionAsset")
            cta_link.asset = cta_asset_name
            info.call_to_actions.append(cta_link)
            paths = [item for item in str(campaign.get("display_path") or "").split("/") if item]
            if paths:
                info.breadcrumb1 = paths[0][:15]
            if len(paths) > 1:
                info.breadcrumb2 = paths[1][:15]
        elif campaign.get("ad_type") == "CAROUSEL":
            logo_asset = next((item for item in image_assets if _image_role(item[1]) == "SQUARE"), image_assets[0])
            info = ad.demand_gen_carousel_ad
            info.business_name = campaign["business_name"]
            info.call_to_action_text = campaign.get("call_to_action") or "LEARN_MORE"
            info.logo_image.asset = logo_asset[0]
            info.headline.text = str((campaign.get("headlines") or [""])[0])
            info.description.text = str((campaign.get("descriptions") or [""])[0])
            card_headlines = campaign.get("carousel_card_headlines") or campaign.get("headlines") or []
            for index, (asset_name, item) in enumerate([row for row in image_assets if row != logo_asset][:10]):
                card_name = client.get_service("AssetService").asset_path(customer_id, next_temp_id)
                next_temp_id -= 1
                card_op = client.get_type("MutateOperation")
                card = card_op.asset_operation.create
                card.resource_name = card_name
                card.name = f"DGU card {campaign['deployment_key'][:12]} {index + 1}"
                card.type_ = client.enums.AssetTypeEnum.DEMAND_GEN_CAROUSEL_CARD
                if _image_role(item) == "SQUARE":
                    card.demand_gen_carousel_card_asset.square_marketing_image_asset = asset_name
                else:
                    card.demand_gen_carousel_card_asset.marketing_image_asset = asset_name
                card.demand_gen_carousel_card_asset.headline = str(
                    card_headlines[index % len(card_headlines)] if card_headlines else campaign["business_name"]
                )[:40]
                card.demand_gen_carousel_card_asset.call_to_action_text = (
                    campaign.get("call_to_action") or "LEARN_MORE"
                )
                card.final_urls.append(campaign["final_url"])
                operations.append(card_op)
                card_link = client.get_type("AdDemandGenCarouselCardAsset")
                card_link.asset = card_name
                info.carousel_cards.append(card_link)
        else:
            info = ad.demand_gen_multi_asset_ad
            info.business_name = campaign["business_name"]
            info.call_to_action_text = campaign.get("call_to_action") or "LEARN_MORE"
            _append_text_assets(client, info.headlines, campaign.get("headlines") or [])
            _append_text_assets(client, info.descriptions, campaign.get("descriptions") or [])
            for asset_name, item in image_assets:
                link = client.get_type("AdImageAsset")
                link.asset = asset_name
                ratio = (item.get("width") or 0) / max(item.get("height") or 1, 1)
                if abs(ratio - 1.0) < 0.08:
                    info.square_marketing_images.append(link)
                    if not info.logo_images:
                        logo_link = client.get_type("AdImageAsset")
                        logo_link.asset = asset_name
                        info.logo_images.append(logo_link)
                elif abs(ratio - 0.8) < 0.08:
                    info.portrait_marketing_images.append(link)
                elif str(item.get("suggested_role") or "").upper() == "CLASSIC_DISPLAY":
                    info.classic_display_images.append(link)
                else:
                    info.marketing_images.append(link)
        operations.append(ad_op)
        return operations

    def start_youtube_video_upload(
        self, customer_id: str, file_path: str, title: str, description: str
    ) -> YouTubeUploadResult:
        with google_ads_client(self.config) as client:
            service = client.get_service("YouTubeVideoUploadService")
            request = client.get_type("CreateYouTubeVideoUploadRequest")
            request.customer_id = customer_id
            request.you_tube_video_upload.video_title = title
            request.you_tube_video_upload.video_description = description
            request.you_tube_video_upload.video_privacy = client.enums.YouTubeVideoPrivacyEnum.UNLISTED
            with Path(file_path).open("rb") as stream:
                response = service.create_you_tube_video_upload(stream=stream, request=request, retry=None)
            return YouTubeUploadResult(
                state="PENDING",
                resource_name=response.resource_name,
                video_id=None,
                message="Видео передано в Google Ads и ожидает обработки YouTube",
            )

    def get_youtube_video_upload(self, customer_id: str, resource_name: str) -> YouTubeUploadResult:
        escaped = resource_name.replace("'", "\\'")
        query = f"""
            SELECT you_tube_video_upload.resource_name,
                   you_tube_video_upload.video_id,
                   you_tube_video_upload.state
            FROM you_tube_video_upload
            WHERE you_tube_video_upload.resource_name = '{escaped}'
        """
        with google_ads_client(self.config) as client:
            service = client.get_service("GoogleAdsService")
            for batch in service.search_stream(customer_id=customer_id, query=query):
                for row in batch.results:
                    state = getattr(row.you_tube_video_upload.state, "name", None) or str(
                        row.you_tube_video_upload.state
                    )
                    return YouTubeUploadResult(
                        state=state,
                        resource_name=row.you_tube_video_upload.resource_name,
                        video_id=row.you_tube_video_upload.video_id or None,
                        message=f"Состояние YouTube upload: {state}",
                    )
        return YouTubeUploadResult(
            state="UNAVAILABLE",
            resource_name=resource_name,
            video_id=None,
            message="Google Ads не вернул ресурс загрузки",
        )


def _append_text_assets(client: Any, target: Any, values: list[str]) -> None:
    for value in values:
        item = client.get_type("AdTextAsset")
        item.text = value
        target.append(item)


def _append_custom_parameters(client: Any, target: Any, values: list[dict]) -> None:
    for value in values:
        key = str(value.get("key") or "").strip()
        parameter_value = str(value.get("value") or "").strip()
        if not key:
            continue
        item = client.get_type("CustomParameter")
        item.key = key
        item.value = parameter_value
        target.append(item)


def _set_bidding(client: Any, target: Any, campaign: dict) -> None:
    strategy = str(campaign.get("bidding_strategy") or "TARGET_CPA").upper()
    target_cpa = int(campaign.get("target_cpa_micros") or 0)
    target_roas = float(campaign.get("target_roas") or 0)
    if target_roas > 10:
        target_roas /= 100
    if strategy == "TARGET_CPA":
        target.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.TARGET_CPA
        target.target_cpa.target_cpa_micros = target_cpa
    elif strategy == "MAXIMIZE_CONVERSIONS":
        target.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.MAXIMIZE_CONVERSIONS
        if target_cpa:
            target.maximize_conversions.target_cpa_micros = target_cpa
    elif strategy == "TARGET_ROAS":
        target.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.TARGET_ROAS
        target.target_roas.target_roas = target_roas
    elif strategy == "MAXIMIZE_CLICKS":
        target.bidding_strategy_type = client.enums.BiddingStrategyTypeEnum.TARGET_SPEND
        ceiling = int(campaign.get("cpc_bid_ceiling_micros") or 0)
        if ceiling:
            target.target_spend.cpc_bid_ceiling_micros = ceiling
    else:
        raise ValueError(f"Стратегия ставок {strategy} недоступна для Demand Gen")


def _configure_channel_controls(client: Any, ad_group: Any, config: dict) -> None:
    mode = str(config.get("mode") or "ALL_CHANNELS").upper()
    controls = ad_group.demand_gen_ad_group_settings.channel_controls
    if mode == "ALL_CHANNELS":
        controls.channel_strategy = client.enums.DemandGenChannelStrategyEnum.ALL_CHANNELS
        return
    if mode in {"GOOGLE_OWNED", "ALL_OWNED_AND_OPERATED_CHANNELS"}:
        controls.channel_strategy = client.enums.DemandGenChannelStrategyEnum.ALL_OWNED_AND_OPERATED_CHANNELS
        return
    if mode not in {"MANUAL", "SELECTED_CHANNELS"}:
        raise ValueError(f"Неизвестный режим channel controls: {mode}")
    selected = config.get("selected") or config.get("selected_channels") or {}
    if selected.get("maps") and "maps" not in controls.selected_channels._meta.fields:
        raise ValueError("Google Maps отсутствует в protobuf-схеме установленного Google Ads Python client")
    supported = ("youtube_in_stream", "youtube_in_feed", "youtube_shorts", "discover", "gmail", "display", "maps")
    enabled = 0
    for field in supported:
        if field not in controls.selected_channels._meta.fields:
            continue
        value = bool(selected.get(field, False))
        setattr(controls.selected_channels, field, value)
        enabled += int(value)
    if not enabled:
        raise ValueError("При ручном выборе каналов нужно включить хотя бы один канал")


def _criterion_operation(
    client: Any,
    ad_group_name: str,
    field_path: str,
    value: object,
    *,
    negative: bool = False,
) -> Any:
    operation = client.get_type("MutateOperation")
    criterion = operation.ad_group_criterion_operation.create
    criterion.ad_group = ad_group_name
    criterion.negative = negative
    target = criterion
    parts = field_path.split(".")
    for part in parts[:-1]:
        target = getattr(target, part)
    setattr(target, parts[-1], value)
    return operation


def _append_demographic_operations(
    client: Any,
    operations: list[Any],
    ad_group_name: str,
    demographics: dict,
) -> None:
    fields = {
        "age_ranges": ("age_range.type_", client.enums.AgeRangeTypeEnum),
        "genders": ("gender.type_", client.enums.GenderTypeEnum),
        "parental_statuses": ("parental_status.type_", client.enums.ParentalStatusTypeEnum),
        "income_ranges": ("income_range.type_", client.enums.IncomeRangeTypeEnum),
    }
    for key, (field_path, enum_type) in fields.items():
        for value in demographics.get(key) or []:
            operations.append(
                _criterion_operation(client, ad_group_name, field_path, getattr(enum_type, str(value).upper()))
            )
        for value in demographics.get(f"excluded_{key}") or []:
            operations.append(
                _criterion_operation(
                    client,
                    ad_group_name,
                    field_path,
                    getattr(enum_type, str(value).upper()),
                    negative=True,
                )
            )


def _append_schedule_operations(
    client: Any,
    operations: list[Any],
    campaign_name: str,
    schedule: list[dict],
) -> None:
    for item in schedule:
        operation = client.get_type("MutateOperation")
        criterion = operation.campaign_criterion_operation.create
        criterion.campaign = campaign_name
        criterion.ad_schedule.day_of_week = getattr(
            client.enums.DayOfWeekEnum,
            str(item.get("day_of_week") or "MONDAY").upper(),
        )
        criterion.ad_schedule.start_hour = int(item.get("start_hour", 0))
        criterion.ad_schedule.start_minute = getattr(
            client.enums.MinuteOfHourEnum,
            str(item.get("start_minute") or "ZERO").upper(),
        )
        criterion.ad_schedule.end_hour = int(item.get("end_hour", 24))
        criterion.ad_schedule.end_minute = getattr(
            client.enums.MinuteOfHourEnum,
            str(item.get("end_minute") or "ZERO").upper(),
        )
        operations.append(operation)


def _google_date_time(value: object) -> str:
    text = str(value).strip()
    if len(text) == 17 and text[8] == " " and text[11] == ":":
        return text
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed.strftime("%Y%m%d %H:%M:%S")


def _image_role(item: dict) -> str:
    ratio = (item.get("width") or 0) / max(item.get("height") or 1, 1)
    if abs(ratio - 1.0) < 0.08:
        return "SQUARE"
    if abs(ratio - 0.8) < 0.08:
        return "PORTRAIT"
    return "LANDSCAPE"


def _escape_gaql(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def asset_cache_key(customer_id: str, sha256: str) -> tuple[str, str]:
    return ("".join(character for character in customer_id if character.isdigit()), sha256.lower())


def _enum_name(value: object) -> str:
    return getattr(value, "name", None) or str(value)


def _resource_names(response: Any) -> list[str]:
    names: list[str] = []
    result_fields = (
        "campaign_budget_result",
        "campaign_result",
        "ad_group_result",
        "ad_group_criterion_result",
        "asset_result",
        "ad_group_ad_result",
    )
    for operation_response in response.mutate_operation_responses:
        for field in result_fields:
            result = getattr(operation_response, field, None)
            resource_name = getattr(result, "resource_name", "") if result is not None else ""
            if resource_name:
                names.append(str(resource_name))
                break
    return names


def _google_exception(exc: Exception, customer_id: str, campaign_name: str | None) -> tuple[list[dict], str | None]:
    try:
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:  # pragma: no cover
        GoogleAdsException = ()  # type: ignore[assignment,misc]
    if isinstance(exc, GoogleAdsException):
        issues = []
        for error in exc.failure.errors:
            issues.append(
                {
                    "customer_id": customer_id,
                    "campaign_name": campaign_name,
                    "code": _google_error_code(error),
                    "message": error.message,
                    "field_path": str(error.location) if error.location else None,
                }
            )
        return issues, exc.request_id
    return (
        [
            {
                "customer_id": customer_id,
                "campaign_name": campaign_name,
                "code": exc.__class__.__name__,
                "message": str(exc),
            }
        ],
        None,
    )


def _google_error_code(error: Any) -> str:
    error_code = error.error_code
    protobuf = getattr(error_code, "_pb", None)
    field_name = protobuf.WhichOneof("error_code") if protobuf is not None else None
    if field_name:
        field = protobuf.DESCRIPTOR.fields_by_name.get(field_name)
        number = getattr(protobuf, field_name)
        enum_value = field.enum_type.values_by_number.get(number) if field and field.enum_type else None
        value_name = enum_value.name if enum_value else _enum_name(getattr(error_code, field_name))
        return f"{field_name.upper()}.{value_name}"
    return str(error_code).strip() or "GOOGLE_ADS_ERROR"


def _connection_check_failure(exc: Exception, customer_id: str, api_version: str) -> AdapterCheckResult:
    message, request_id = _google_ads_failure_message(
        exc,
        customer_id,
        f"Проверка MCC {customer_id} не пройдена",
    )
    return AdapterCheckResult(
        ok=False,
        status="ERROR",
        message=message,
        api_version=api_version,
        request_id=request_id,
    )


def _google_ads_failure_message(exc: Exception, customer_id: str, prefix: str) -> tuple[str, str | None]:
    issues, request_id = _google_exception(exc, customer_id, None)
    codes = sorted({str(issue.get("code") or "GOOGLE_ADS_ERROR") for issue in issues})
    messages = [str(issue.get("message") or "").strip() for issue in issues]
    google_message = "; ".join(message for message in messages if message) or str(exc)
    explanation = _connection_error_explanation(codes)
    request_part = f" Request ID: {request_id}." if request_id else ""
    return (
        (
            f"{prefix}. Код Google Ads: {', '.join(codes)}. {explanation} "
            f"Сообщение Google: {google_message}.{request_part}"
        ),
        request_id,
    )


def _connection_error_explanation(codes: list[str]) -> str:
    joined = " ".join(codes)
    if "USER_PERMISSION_DENIED" in joined:
        return "Пользователь OAuth не имеет доступа к этому MCC или указан неверный login customer ID."
    if "DEVELOPER_TOKEN_INVALID" in joined:
        return "Сохранённый Developer Token отклонён Google как недействительный."
    if "DEVELOPER_TOKEN_NOT_APPROVED" in joined:
        return "Developer Token не имеет уровня доступа, необходимого для этого аккаунта."
    if "CUSTOMER_NOT_ENABLED" in joined:
        return "Указанный аккаунт Google Ads не активирован."
    if "AUTHENTICATION_ERROR" in joined or "OAUTH_TOKEN_HEADER_INVALID" in joined:
        return "Google отклонил сохранённые OAuth-реквизиты."
    return "Google Ads отклонил безопасный запрос чтения; код и Request ID указаны для диагностики."

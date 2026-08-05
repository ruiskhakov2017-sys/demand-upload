from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.db.models import User
from app.google_ads.capability_registry import (
    CURRENT_GOOGLE_ADS_API_VERSION,
    get_demand_gen_capabilities,
    get_demand_gen_capability_registry,
)
from app.google_ads.method_capabilities import get_adapter_method_capabilities

router = APIRouter(prefix="/google-ads/capabilities", tags=["google-ads"])


@router.get("")
def get_capabilities(
    api_version: str = Query(default=CURRENT_GOOGLE_ADS_API_VERSION, max_length=24),
    user: User = Depends(get_current_user),
) -> dict:
    return {
        "summary": get_demand_gen_capabilities(api_version).__dict__,
        "fields": get_demand_gen_capability_registry(api_version),
        "methods": get_adapter_method_capabilities(api_version),
        "production_major_auto_upgrade": False,
    }

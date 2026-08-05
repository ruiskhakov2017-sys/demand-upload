from app.google_ads.interface import GoogleAdsConnectionConfig
from app.google_ads.versions.v24_2.adapter import GoogleAdsV242Adapter


class GoogleAdsV25Adapter(GoogleAdsV242Adapter):
    """v25 boundary for adapter-neutral control-center operations.

    The current control-center query contract only uses fields shared with
    v24.2. Keeping a separate class lets v25 evolve without leaking proto
    types into services or persistence models.
    """

    contract_version = "v25"

    def __init__(self, config: GoogleAdsConnectionConfig) -> None:
        if not config.api_version.lower().startswith("v25"):
            raise ValueError("GoogleAdsV25Adapter принимает только конфигурацию API v25")
        super().__init__(config)

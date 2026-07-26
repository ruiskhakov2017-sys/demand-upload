class GoogleAdsAdapterError(RuntimeError):
    """Base adapter error that is safe to show after redaction."""


class GoogleAdsCredentialsError(GoogleAdsAdapterError):
    """Raised when a connection does not have enough credentials to call Google Ads API."""

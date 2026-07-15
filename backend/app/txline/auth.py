from __future__ import annotations

from app.config import Settings


class TxLineConfigurationError(RuntimeError):
    """Raised when TxLINE integration is called without enough configuration."""


def build_auth_headers(settings: Settings) -> dict[str, str]:
    if not (settings.txline_guest_jwt or settings.txline_api_token):
        raise TxLineConfigurationError("TxLINE credentials are not configured.")

    headers: dict[str, str] = {}
    if settings.txline_guest_jwt:
        headers["Authorization"] = f"Bearer {settings.txline_guest_jwt}"
    if settings.txline_api_token:
        headers["X-Api-Token"] = settings.txline_api_token
    return headers

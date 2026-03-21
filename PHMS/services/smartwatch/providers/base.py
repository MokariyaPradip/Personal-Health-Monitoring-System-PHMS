from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from services.smartwatch.contracts import FetchContext, NormalizedHealthPayload, TokenBundle


class SmartwatchProviderAdapter(ABC):
    """Contract for provider integrations (Google Fit, Fitbit, etc.)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable provider identifier (for example: 'google_fit')."""

    @abstractmethod
    def build_authorization_url(self, user_id: int, redirect_uri: str, state: str) -> str:
        """Create provider consent URL for frontend redirect."""

    @abstractmethod
    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> TokenBundle:
        """Exchange OAuth authorization code for provider tokens."""

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> TokenBundle:
        """Refresh an expired access token using provider refresh token."""

    @abstractmethod
    def fetch_health_payloads(self, context: FetchContext) -> list[NormalizedHealthPayload]:
        """Fetch and normalize provider health samples into canonical payloads."""

    def normalize_timestamp(self, timestamp: datetime | None) -> datetime | None:
        """Hook for provider-specific timestamp normalization."""
        return timestamp

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TokenBundle:
    """Credential payload required to call a provider API for one user."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scope: str | None = None
    provider_user_id: str | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return True when access token is known to be expired."""
        if self.expires_at is None:
            return False
        now = now or datetime.utcnow()
        return now >= self.expires_at


@dataclass(slots=True)
class NormalizedHealthPayload:
    """Provider-independent health metrics aligned to existing add_health inputs."""

    heart_rate: int | None = None
    temperature: float | None = None
    steps: int | None = None
    sleep_hours: float | None = None
    blood_pressure: float | None = None
    sugar: float | None = None
    observed_at: datetime | None = None
    source_record_id: str | None = None
    provider: str | None = None
    raw_payload: dict[str, Any] | None = None

    def to_health_service_payload(self) -> dict[str, int | float | None]:
        """Convert to the exact shape consumed by health_service.add_health."""
        return {
            'heart_rate': self.heart_rate,
            'temperature': self.temperature,
            'steps': self.steps,
            'sleep_hours': self.sleep_hours,
            'blood_pressure': self.blood_pressure,
            'sugar': self.sugar,
        }


@dataclass(slots=True)
class FetchContext:
    """Input context used by provider adapters during sync fetch."""

    user_id: int
    provider: str
    token: TokenBundle
    cursor: str | None = None
    since: datetime | None = None


@dataclass(slots=True)
class SyncRequest:
    """Orchestrator request to sync one user/provider."""

    user_id: int
    provider: str
    cursor: str | None = None
    since: datetime | None = None
    dry_run: bool = False


@dataclass(slots=True)
class SyncResult:
    """Summary produced by the sync orchestrator."""

    success: bool
    provider: str
    user_id: int
    fetched_count: int = 0
    ingested_count: int = 0
    deduplicated_count: int = 0
    failed_count: int = 0
    errors: list[str] = field(default_factory=list)
    status_message: str = ''

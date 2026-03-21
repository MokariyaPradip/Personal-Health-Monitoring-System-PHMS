from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from services.health_service import ingest_health_entry
from services.smartwatch.contracts import NormalizedHealthPayload


class HealthIngestionGateway(ABC):
    """Contract for writing normalized provider data into the existing health flow."""

    @abstractmethod
    def ingest(self, user_id: int, payload: NormalizedHealthPayload) -> dict[str, Any]:
        """Ingest one normalized payload and return service response."""


class ExistingHealthServiceGateway(HealthIngestionGateway):
    """Adapter that routes smartwatch payloads into the canonical health ingestion service."""

    def ingest(self, user_id: int, payload: NormalizedHealthPayload) -> dict[str, Any]:
        # This preserves current validation, scoring, ML prediction, alert, and email behavior.
        return ingest_health_entry(
            user_id,
            payload.to_health_service_payload(),
            source='smartwatch',
            ingestion_metadata={
                'data_source': payload.provider or 'smartwatch',
                'source_record_id': payload.source_record_id,
                'observed_at': payload.observed_at,
            },
        )

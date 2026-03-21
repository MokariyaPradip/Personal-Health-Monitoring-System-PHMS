from __future__ import annotations

from abc import ABC, abstractmethod

from services.smartwatch.contracts import TokenBundle


class TokenManager(ABC):
    """Persistence contract for provider credentials."""

    @abstractmethod
    def get_token_bundle(self, user_id: int, provider: str) -> TokenBundle | None:
        """Return saved provider credentials for one user/provider pair."""

    @abstractmethod
    def save_token_bundle(self, user_id: int, provider: str, token_bundle: TokenBundle) -> None:
        """Persist provider credentials for a user/provider pair."""

    @abstractmethod
    def revoke_token_bundle(self, user_id: int, provider: str) -> None:
        """Remove provider credentials for a user/provider pair."""


class InMemoryTokenManager(TokenManager):
    """Foundation-only in-memory token manager for local orchestration wiring."""

    def __init__(self) -> None:
        self._store: dict[tuple[int, str], TokenBundle] = {}

    def get_token_bundle(self, user_id: int, provider: str) -> TokenBundle | None:
        return self._store.get((user_id, provider))

    def save_token_bundle(self, user_id: int, provider: str, token_bundle: TokenBundle) -> None:
        self._store[(user_id, provider)] = token_bundle

    def revoke_token_bundle(self, user_id: int, provider: str) -> None:
        self._store.pop((user_id, provider), None)

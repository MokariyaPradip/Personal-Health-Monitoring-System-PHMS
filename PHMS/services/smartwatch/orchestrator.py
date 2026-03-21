from __future__ import annotations

import logging

from services.smartwatch.contracts import FetchContext, SyncRequest, SyncResult
from services.smartwatch.ingestion_gateway import HealthIngestionGateway
from services.smartwatch.providers.base import SmartwatchProviderAdapter
from services.smartwatch.token_manager import TokenManager
from services.smartwatch.retry_utils import retry_with_backoff, SyncErrorContext, is_transient_error

logger = logging.getLogger(__name__)


class SmartwatchSyncOrchestrator:
    """Coordinates provider fetch and ingestion through the existing health service."""

    def __init__(
        self,
        *,
        token_manager: TokenManager,
        ingestion_gateway: HealthIngestionGateway,
        adapters: list[SmartwatchProviderAdapter] | None = None,
    ) -> None:
        self._token_manager = token_manager
        self._ingestion_gateway = ingestion_gateway
        self._adapters: dict[str, SmartwatchProviderAdapter] = {}

        for adapter in adapters or []:
            self.register_adapter(adapter)

    def register_adapter(self, adapter: SmartwatchProviderAdapter) -> None:
        self._adapters[adapter.provider_name] = adapter

    def get_adapter(self, provider: str) -> SmartwatchProviderAdapter | None:
        return self._adapters.get(provider)

    def sync_user(self, request: SyncRequest) -> SyncResult:
        """Sync health data for a user with retry and error recovery.
        
        Implements exponential backoff retry for transient API failures,
        automatic token refresh, and detailed error tracking.
        """
        error_context = SyncErrorContext(request.user_id, request.provider)
        
        adapter = self.get_adapter(request.provider)
        if adapter is None:
            return SyncResult(
                success=False,
                provider=request.provider,
                user_id=request.user_id,
                errors=[f'No adapter registered for provider: {request.provider}'],
                status_message='Adapter not registered',
            )

        token_bundle = self._token_manager.get_token_bundle(request.user_id, request.provider)
        if token_bundle is None:
            error_context.add_error(
                'AccountNotFound',
                f'No token bundle found for user_id={request.user_id}',
                is_retryable=False,
            )
            return SyncResult(
                success=False,
                provider=request.provider,
                user_id=request.user_id,
                errors=[f'No token bundle found for provider: {request.provider}'],
                status_message='Not connected',
            )

        # Token refresh with retry
        max_refresh_attempts = 2
        for refresh_attempt in range(max_refresh_attempts):
            if token_bundle.is_expired() and token_bundle.refresh_token:
                try:
                    logger.info(
                        f'Attempting token refresh (attempt {refresh_attempt+1}/{max_refresh_attempts}) '
                        f'for user_id={request.user_id}, provider={request.provider}'
                    )
                    refreshed = adapter.refresh_access_token(token_bundle.refresh_token)
                    self._token_manager.save_token_bundle(request.user_id, request.provider, refreshed)
                    token_bundle = refreshed
                    error_context.mark_token_refreshed()
                    logger.info(f'✓ Token refresh succeeded for user_id={request.user_id}')
                    break
                except Exception as e:
                    error_context.add_error(
                        'TokenRefreshFailed',
                        f'Failed to refresh token: {str(e)}',
                        attempt=refresh_attempt,
                        is_retryable=is_transient_error(e),
                    )
                    logger.warning(
                        f"⚠️ Token refresh failed (attempt {refresh_attempt+1}/{max_refresh_attempts}): {str(e)}"
                    )
                    
                    # Check if this is a permanent auth failure
                    if not is_transient_error(e):
                        logger.error(f"✗ Permanent token refresh failure for user_id={request.user_id}")
                        error_summary = error_context.get_summary(success=False)
                        return SyncResult(
                            success=False,
                            provider=request.provider,
                            user_id=request.user_id,
                            errors=[error_summary],
                            status_message='Token refresh failed - account disconnection recommended',
                        )
                    
                    if refresh_attempt < max_refresh_attempts - 1:
                        error_context.mark_retry()

        # Fetch with retry
        context = FetchContext(
            user_id=request.user_id,
            provider=request.provider,
            token=token_bundle,
            cursor=request.cursor,
            since=request.since,
        )
        
        payloads = self._fetch_with_retry(adapter, context, error_context, max_retries=3)
        
        if payloads is None:
            # Fetch failed permanently
            error_summary = error_context.get_summary(success=False)
            return SyncResult(
                success=False,
                provider=request.provider,
                user_id=request.user_id,
                errors=[error_summary],
                status_message='Failed to fetch data from provider',
            )

        result = SyncResult(
            success=True,
            provider=request.provider,
            user_id=request.user_id,
            fetched_count=len(payloads),
            status_message='Sync completed',
        )

        # Ingest payloads
        for payload in payloads:
            if request.dry_run:
                result.ingested_count += 1
                continue

            service_result = self._ingestion_gateway.ingest(request.user_id, payload)
            if service_result.get('success'):
                if service_result.get('deduplicated'):
                    result.deduplicated_count += 1
                else:
                    result.ingested_count += 1
            else:
                result.failed_count += 1
                error_message = service_result.get('message', 'Unknown ingestion error')
                result.errors.append(error_message)

        if result.failed_count > 0:
            result.success = False
            result.status_message = 'Sync completed with ingestion failures'
        
        # Update status message with retry history if applicable
        if error_context.retry_attempts > 0:
            result.status_message = f'{result.status_message} (succeeded after {error_context.retry_attempts} retries)'

        return result

    def _fetch_with_retry(
        self,
        adapter: SmartwatchProviderAdapter,
        context: FetchContext,
        error_context: SyncErrorContext,
        max_retries: int = 3,
    ) -> list | None:
        """Fetch health payloads with exponential backoff retry.
        
        Returns:
            list: Fetched payloads on success
            None: On permanent failure after retries
        """
        base_delay = 1.0
        backoff_factor = 2.0
        max_delay = 8.0
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.debug(f'Fetch retry attempt {attempt}/{max_retries} for user_id={context.user_id}')
                
                payloads = adapter.fetch_health_payloads(context)
                
                if attempt > 0:
                    logger.info(
                        f'✓ Fetch succeeded on retry attempt {attempt} for user_id={context.user_id}'
                    )
                
                return payloads
            
            except Exception as e:
                error_type = type(e).__name__
                is_retryable = is_transient_error(e)
                
                error_context.add_error(
                    error_type,
                    str(e),
                    attempt=attempt,
                    is_retryable=is_retryable,
                )
                
                # Check if error is permanent
                if not is_retryable or attempt >= max_retries:
                    logger.error(
                        f"✗ Fetch failed with {'permanent' if not is_retryable else 'final'} error "
                        f"(attempt {attempt+1}/{max_retries+1}) for user_id={context.user_id}: {error_type}: {str(e)}",
                        exc_info=True,
                    )
                    return None
                
                # Calculate delay and retry
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                logger.warning(
                    f"⚠️ Fetch failed (attempt {attempt+1}/{max_retries+1}) for user_id={context.user_id}: "
                    f"{error_type}. Retrying in {delay:.1f}s... ({str(e)[:60]})"
                )
                
                error_context.mark_retry()
                import time
                time.sleep(delay)
        
        return None

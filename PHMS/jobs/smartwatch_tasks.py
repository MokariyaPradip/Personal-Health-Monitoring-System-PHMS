"""Background job callbacks for smartwatch sync workflows.

Jobs in this module delegate to service-layer logic only. Implements robust
error handling with structured error recording, retry logic, and non-blocking
failure isolation per account.
"""

import logging
from datetime import datetime

from repositories.smartwatch_repository import SmartwatchRepository
from services.smartwatch_service import trigger_sync

logger = logging.getLogger(__name__)


def sync_all_connected_smartwatches():
    """Periodic job: Sync all connected smartwatch accounts with resilience.
    
    Fetches all connected accounts and triggers sync for each with robust error
    handling. Failures are isolated per-account and recorded in structured format
    for UI visibility. Does not break scheduler loop on any failure.
    
    Returns:
        dict: Status summary with keys:
            - status (str): 'success' or 'error'
            - message (str): Summary message
            - synced_count (int): Successfully synced accounts
            - failed_count (int): Failed accounts
            - total_accounts (int): Total connected accounts
            - retry_attempts (int): Total retry attempts across all accounts
            - errors (list[dict] | None): Detailed error info per failed account
            - completed_at (str): ISO timestamp when job completed
    """
    try:
        accounts = SmartwatchRepository.get_all_connected_accounts()
        
        if not accounts:
            logger.info("✓ No connected smartwatch accounts to sync")
            return {
                'status': 'success',
                'message': 'No connected accounts',
                'synced_count': 0,
                'failed_count': 0,
                'total_accounts': 0,
                'retry_attempts': 0,
                'errors': None,
                'completed_at': datetime.now().isoformat(),
            }
        
        logger.info(f"Starting periodic smartwatch sync for {len(accounts)} connected account(s)")
        
        synced_count = 0
        failed_count = 0
        retry_attempts = 0
        detailed_errors = []
        
        for account in accounts:
            try:
                logger.debug(
                    f"Syncing account: user_id={account.user_id}, provider={account.provider}"
                )
                
                # Trigger sync using existing service with resilience
                sync_result = trigger_sync(
                    user_id=account.user_id,
                    provider=account.provider,
                    cursor=None,  # Use incremental cursor from sync state
                    since=None,   # Use incremental since from sync state
                )
                
                # Determine if sync succeeded
                # trigger_sync returns dict with 'success' key (bool) or 'status' key ('success'/'error')
                sync_success = (
                    sync_result.get('success') or 
                    sync_result.get('status') == 'success'
                )
                
                if sync_success:
                    synced_count += 1
                    entries_fetched = 0
                    
                    # Try to extract fetch count from various response formats
                    if 'sync_result' in sync_result and isset(sync_result['sync_result']):
                        entries_fetched = sync_result['sync_result'].get('fetched_count', 0)
                    elif 'entries_fetched' in sync_result:
                        entries_fetched = sync_result['entries_fetched']
                    
                    logger.info(
                        f"✓ Synced account: user_id={account.user_id}, provider={account.provider}, "
                        f"fetched={entries_fetched} entries"
                    )
                    
                    # Log any retry information if present
                    message = sync_result.get('message', '')
                    if 'retry' in message.lower() or 'retried' in message.lower():
                        logger.info(f"  (with resilience: {message})")
                
                else:
                    failed_count += 1
                    error_msg = sync_result.get('message', 'Unknown error')
                    
                    # Extract retry count if available
                    retries = 0
                    try:
                        # Some error messages may include retry info like "failed after 2 retries"
                        import re
                        match = re.search(r'(\d+)\s+retr', error_msg)
                        if match:
                            retries = int(match.group(1))
                            retry_attempts += retries
                    except Exception:
                        pass
                    
                    detailed_errors.append({
                        'user_id': account.user_id,
                        'provider': account.provider,
                        'error': error_msg,
                        'retry_attempts': retries,
                    })
                    
                    logger.warning(
                        f"⚠️ Sync failed: user_id={account.user_id}, provider={account.provider}, "
                        f"error={error_msg}"
                    )
                        
            except Exception as exc:
                failed_count += 1
                error_msg = str(exc)
                detailed_errors.append({
                    'user_id': account.user_id,
                    'provider': account.provider,
                    'error': f'Exception during sync: {error_msg}',
                    'retry_attempts': 0,
                })
                logger.error(
                    f"❌ Exception during sync for user_id={account.user_id}, provider={account.provider}: {error_msg}",
                    exc_info=True,
                )
        
        summary = {
            'status': 'success' if failed_count == 0 else 'partial_failure',
            'message': f'Synced {synced_count}/{len(accounts)} accounts'
                       + (f' ({failed_count} failed)' if failed_count > 0 else ''),
            'synced_count': synced_count,
            'failed_count': failed_count,
            'total_accounts': len(accounts),
            'retry_attempts': retry_attempts,
            'errors': detailed_errors if detailed_errors else None,
            'completed_at': datetime.now().isoformat(),
        }
        
        if failed_count == 0:
            logger.info(
                f"✓ Periodic smartwatch sync complete: synced {synced_count}/{len(accounts)}"
            )
        else:
            logger.warning(
                f"⚠️ Periodic smartwatch sync complete with failures: "
                f"synced {synced_count}/{len(accounts)}, failed {failed_count}"
            )
        
        return summary
        
    except Exception as exc:
        error_msg = f"Fatal error in periodic smartwatch sync: {str(exc)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        return {
            'status': 'error',
            'message': error_msg,
            'synced_count': 0,
            'failed_count': 0,
            'total_accounts': 0,
            'retry_attempts': 0,
            'errors': [{'error': error_msg}],
            'completed_at': datetime.now().isoformat(),
        }


def isset(value) -> bool:
    """Check if value is not None and is not empty/falsy for dict checks."""
    return value is not None

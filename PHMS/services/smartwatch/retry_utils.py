"""Retry strategies and exponential backoff utilities for smartwatch sync operations.

This module provides retry decorators and helpers for handling transient failures
in smartwatch provider API calls (network errors, rate limits, timeouts).

Features:
    - Exponential backoff with jitter
    - Configurable max retries and base delay
    - Transient error detection (retryable vs permanent)
    - Detailed logging of retry attempts
    - Token expiration and refresh handling
"""

import logging
import time
from typing import Callable, TypeVar, Any
from functools import wraps

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


class TransientError(Exception):
    """Raised for errors that should be retried (network, rate limits, timeouts)."""
    pass


class PermanentError(Exception):
    """Raised for errors that should not be retried (auth, not found, invalid input)."""
    pass


def is_transient_error(exception: Exception) -> bool:
    """Determine if an exception represents a transient (retryable) error.
    
    Transient errors include:
        - Network timeouts and connection errors
        - HTTP 429 (rate limit), 502 (bad gateway), 503 (service unavailable), 504 (gateway timeout)
        - API temporary failures
        - Database connection errors
    
    Permanent errors include:
        - Auth errors (401 Unauthorized, 403 Forbidden)
        - 404 Not Found
        - Invalid input (400 Bad Request)
        - Other 4xx errors (client errors)
    """
    error_msg = str(exception).lower()
    
    # Timeout and connection errors - transient
    if any(keyword in error_msg for keyword in ['timeout', 'connection', 'network', 'refused']):
        return True
    
    # Rate limit and service errors - transient
    if any(code in error_msg for code in ['429', '502', '503', '504', 'rate limit', 'service unavailable']):
        return True
    
    # Auth errors - permanent
    if any(code in error_msg for code in ['401', '403', 'unauthorized', 'forbidden', 'invalid token']):
        return False
    
    # Not found or client errors - permanent
    if any(code in error_msg for code in ['404', '400', 'not found', 'bad request']):
        return False
    
    # Default: assume transient to be safe
    return True


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    backoff_factor: float = 2.0,
) -> Callable[[F], F]:
    """Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries (int): Maximum number of retry attempts (default 3)
        base_delay (float): Initial delay in seconds (default 1.0)
        max_delay (float): Maximum delay cap in seconds (default 8.0)
        backoff_factor (float): Multiplier for delay between retries (default 2.0)
    
    Returns:
        Callable: Decorated function that retries on transient errors
    
    Behavior:
        - On first call failure: wait base_delay, then retry
        - On second failure: wait base_delay * backoff_factor, then retry
        - On third failure: wait min(base_delay * backoff_factor^2, max_delay), then give up
        - Logs each retry attempt with elapsed time and error
        - Re-raises after max_retries exceeded
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def fetch_from_api(url):
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            last_exception = None
            
            while attempt <= max_retries:
                try:
                    if attempt > 0:
                        logger.debug(
                            f"Retry attempt {attempt}/{max_retries} for {func.__name__}"
                        )
                    
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(
                            f"✓ {func.__name__} succeeded on retry attempt {attempt}"
                        )
                    
                    return result
                
                except Exception as e:
                    last_exception = e
                    
                    # Check if error is transient (retryable)
                    if not is_transient_error(e) or attempt >= max_retries:
                        logger.error(
                            f"✗ {func.__name__} failed with permanent/final error: {str(e)}",
                            exc_info=True,
                        )
                        raise
                    
                    # Calculate delay for next retry
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    logger.warning(
                        f"⚠️ {func.__name__} failed (attempt {attempt+1}/{max_retries+1}): {type(e).__name__}. "
                        f"Retrying in {delay:.1f}s... ({str(e)[:80]})"
                    )
                    
                    time.sleep(delay)
                    attempt += 1
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper  # type: ignore
    
    return decorator


class SyncErrorContext:
    """Structured recording of sync attempt errors and recovery info.
    
    Used to build detailed error messages with retry history, error codes,
    and recovery suggestions for UI visibility and debugging.
    """
    
    def __init__(self, user_id: int, provider: str):
        self.user_id = user_id
        self.provider = provider
        self.errors: list[dict[str, Any]] = []
        self.retry_attempts = 0
        self.token_refreshed = False
        
    def add_error(
        self,
        error_type: str,
        message: str,
        attempt: int = 0,
        is_retryable: bool = True,
    ) -> None:
        """Record a single error with context.
        
        Args:
            error_type (str): Error class name or category (e.g., 'TokenExpired', 'NetworkTimeout')
            message (str): Error message
            attempt (int): Retry attempt number (0 for first attempt)
            is_retryable (bool): Whether this error is retryable
        """
        self.errors.append({
            'type': error_type,
            'message': message,
            'attempt': attempt,
            'retryable': is_retryable,
            'timestamp': time.time(),
        })
    
    def mark_token_refreshed(self) -> None:
        """Record that token refresh was attempted."""
        self.token_refreshed = True
    
    def mark_retry(self) -> None:
        """Increment retry attempt counter."""
        self.retry_attempts += 1
    
    def get_summary(self, success: bool = False) -> str:
        """Get a structured error summary for storage/UI.
        
        Returns:
            str: Formatted error summary with retry history
        
        Example:
            "Sync failed after 2 retries. Errors: [TokenExpired (attempt 0), NetworkTimeout (attempt 1)]"
        """
        if success:
            if self.retry_attempts > 0:
                return f"Sync succeeded after {self.retry_attempts} retry attempt(s)"
            return "Sync succeeded"
        
        if not self.errors:
            return "Sync failed: unknown error"
        
        error_summary = ", ".join(
            f"{e['type']} (attempt {e['attempt']})" for e in self.errors
        )
        
        prefix = f"Sync failed after {self.retry_attempts} retry attempt(s)" \
            if self.retry_attempts > 0 else "Sync failed"
        
        if self.token_refreshed:
            return f"{prefix}. Errors: [{error_summary}]. Token refresh attempted."
        
        return f"{prefix}. Errors: [{error_summary}]."

"""Retry utility module with exponential backoff."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryConfig:
    """Retry configuration.

    Attributes:
        max_attempts: Maximum number of attempts (default: 3).
            This is the total number of tries, not the number of retries.
            For example, max_attempts=3 means: try once, then retry up to 2 times.
        base_delay: Initial delay in seconds (default: 1.0)
        backoff_multiplier: Exponential backoff multiplier (default: 2.0)

    Example:
        config = RetryConfig(max_attempts=5, base_delay=0.5)

    Raises:
        ValueError: If validation fails
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {self.max_attempts}")
        if self.base_delay <= 0:
            raise ValueError(f"base_delay must be > 0, got {self.base_delay}")
        if self.backoff_multiplier < 1.0:
            raise ValueError(f"backoff_multiplier must be >= 1.0, got {self.backoff_multiplier}")


def is_rate_limit_error(e: Exception) -> bool:
    """Check if the exception is a rate limit error.

    Detects rate limit errors by checking for common patterns:
    - "rate limit" in error message
    - "429" in error message
    - "too many requests" in error message

    Args:
        e: The exception to check

    Returns:
        True if the exception appears to be a rate limit error
    """
    error_message = str(e).lower()
    return (
        "rate limit" in error_message
        or "429" in error_message
        or "too many requests" in error_message
    )


def with_retry[T](
    func: Callable[[], T],
    config: RetryConfig | None = None,
    is_retryable: Callable[[Exception], bool] | None = None,
    log: logging.Logger | None = None,
    context: str | None = None,
) -> T:
    """Execute function with exponential backoff retry.

    Args:
        func: The function to execute
        config: Retry configuration (defaults to RetryConfig())
        is_retryable: Function to check if an exception is retryable
            (defaults to is_rate_limit_error)
        log: Logger instance (defaults to module logger)
        context: Optional context string for log messages (e.g., package name)

    Returns:
        The result of the function call

    Raises:
        Exception: The last exception if all retries fail, or immediately
            if the exception is not retryable
    """
    if config is None:
        config = RetryConfig()
    if is_retryable is None:
        is_retryable = is_rate_limit_error
    if log is None:
        log = logger

    last_exception: Exception | None = None
    context_prefix = f"{context}: " if context else ""

    for attempt in range(config.max_attempts):
        try:
            return func()
        except Exception as e:
            last_exception = e

            # Check if error is retryable
            if not is_retryable(e):
                raise

            # Check if we have attempts left
            if attempt >= config.max_attempts - 1:
                raise

            # Calculate delay with exponential backoff
            delay = config.base_delay * (config.backoff_multiplier**attempt)
            log.warning(
                f"{context_prefix}Rate limit hit, retrying in {delay}s "
                f"(attempt {attempt + 1}/{config.max_attempts})"
            )
            time.sleep(delay)

    # Should not reach here, but for type safety
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected: no attempts made")

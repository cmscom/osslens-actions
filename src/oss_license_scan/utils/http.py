"""HTTP client utility module with shared configuration."""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class HttpClientConfig:
    """HTTP client configuration.

    Attributes:
        timeout: Request timeout in seconds (default: 10.0)
        user_agent: User-Agent header value (default: "oss-license-scan")
        follow_redirects: Whether to follow redirects (default: False)

    Example:
        config = HttpClientConfig(timeout=5.0, follow_redirects=True)

    Raises:
        ValueError: If validation fails
    """

    timeout: float = 10.0
    user_agent: str = "oss-license-scan"
    follow_redirects: bool = False

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {self.timeout}")
        if not self.user_agent:
            raise ValueError("user_agent must not be empty")


@contextmanager
def http_client(
    config: HttpClientConfig | None = None,
) -> Generator[httpx.Client]:
    """Create an HTTP client with shared configuration.

    Args:
        config: HTTP client configuration (defaults to HttpClientConfig())

    Yields:
        Configured httpx.Client instance

    Example:
        with http_client() as client:
            response = client.get(url)

        # With custom config
        config = HttpClientConfig(timeout=5.0, follow_redirects=True)
        with http_client(config) as client:
            response = client.get(url)
    """
    if config is None:
        config = HttpClientConfig()

    client = httpx.Client(
        timeout=config.timeout,
        headers={"User-Agent": config.user_agent},
        follow_redirects=config.follow_redirects,
    )

    try:
        yield client
    finally:
        client.close()

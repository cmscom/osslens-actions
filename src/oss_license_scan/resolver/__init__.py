"""License resolution functions for fast and deep modes."""

from oss_license_scan.resolver.cache import DEFAULT_CACHE_TTL_HOURS, SourceCacheEntry
from oss_license_scan.resolver.fast import resolve_fast

__all__ = ["SourceCacheEntry", "DEFAULT_CACHE_TTL_HOURS", "resolve_fast"]

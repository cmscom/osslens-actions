"""RubyGems search tool for license information."""

import time
from typing import Any

import httpx


def rubygems_search(package_name: str, version: str | None = None) -> dict[str, Any]:
    """
    Search RubyGems.org for gem license information.

    Args:
        package_name: Gem name to search.
        version: Optional specific version to search.

    Returns:
        Dict with search results:
            - success: bool - Whether search succeeded
            - package_name: str - Package name searched
            - license: str - License name (or "Unknown")
            - version: str - Package version (if found)
            - homepage_url: str - Homepage URL (if found)
            - source: str - Always "rubygems"
            - error: str - Error message (if failed)
    """
    url = f"https://rubygems.org/api/v1/gems/{package_name}.json"

    # Retry configuration with exponential backoff
    max_retries = 3
    base_delay = 0.5  # 500ms

    for attempt in range(max_retries):
        try:
            # Make request with 5 second timeout
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)

                # Handle various HTTP status codes
                if response.status_code == 404:
                    return {
                        "success": False,
                        "package_name": package_name,
                        "error": "Gem not found on RubyGems.org",
                    }

                if response.status_code == 429:
                    return {
                        "success": False,
                        "package_name": package_name,
                        "error": "Rate limit exceeded",
                    }

                if response.status_code >= 500:
                    return {
                        "success": False,
                        "package_name": package_name,
                        "error": f"RubyGems server error: {response.status_code}",
                    }

                # Success - parse JSON
                response.raise_for_status()
                data = response.json()

                # Extract license from licenses array
                license_name = _extract_rubygems_license(data)

                # Default to "Unknown" if empty
                if not license_name:
                    license_name = "Unknown"

                # Extract homepage URL
                homepage_url = data.get("homepage_uri", "")

                # If no homepage, try source_code_uri
                if not homepage_url:
                    homepage_url = data.get("source_code_uri", "")

                result: dict[str, Any] = {
                    "success": True,
                    "package_name": data.get("name", package_name),
                    "license": license_name,
                    "source": "rubygems",
                }

                if "version" in data:
                    result["version"] = data["version"]

                if homepage_url:
                    result["homepage_url"] = homepage_url

                return result

        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                time.sleep(delay)
                continue

            return {
                "success": False,
                "package_name": package_name,
                "error": "Request timeout while searching RubyGems",
            }

        except httpx.NetworkError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                time.sleep(delay)
                continue

            return {
                "success": False,
                "package_name": package_name,
                "error": f"Network error: {e!s}",
            }

        except Exception as e:
            return {
                "success": False,
                "package_name": package_name,
                "error": f"Unexpected error: {e!s}",
            }

    return {
        "success": False,
        "package_name": package_name,
        "error": "Max retries exceeded",
    }


def _extract_rubygems_license(gem_info: dict[str, Any]) -> str | None:
    """
    Extract license name from RubyGems gem info.

    RubyGems licenses field is an array of strings.

    Args:
        gem_info: Gem info from RubyGems API

    Returns:
        License name, or None if not found
    """
    licenses = gem_info.get("licenses")
    if not licenses:
        return None

    if isinstance(licenses, list):
        if len(licenses) == 0:
            return None
        elif len(licenses) == 1:
            return licenses[0]
        else:
            # Multiple licenses - return SPDX expression
            return " OR ".join(licenses)

    return None

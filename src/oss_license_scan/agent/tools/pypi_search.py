"""PyPI search tool for license information."""

import re
import time
from typing import Any

import httpx


def pypi_search(package_name: str, version: str | None = None) -> dict[str, Any]:
    """
    Search PyPI for package license information.

    Args:
        package_name: Package name to search.
        version: Optional specific version to search.

    Returns:
        Dict with search results:
            - success: bool - Whether search succeeded
            - package_name: str - Package name searched
            - license: str - License name (or "Unknown")
            - version: str - Package version (if found)
            - homepage_url: str - Homepage URL (if found)
            - license_text_url: str - URL to license file (if found)
            - source: str - Always "pypi"
            - error: str - Error message (if failed)
    """
    # Build PyPI API URL
    if version:
        url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    else:
        url = f"https://pypi.org/pypi/{package_name}/json"

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
                        "error": "Package not found on PyPI",
                    }

                if response.status_code == 429:
                    return {
                        "success": False,
                        "package_name": package_name,
                        "error": "Rate limit exceeded",
                    }

                if response.status_code >= 500:
                    # Server error - return immediately (not worth retrying)
                    return {
                        "success": False,
                        "package_name": package_name,
                        "error": f"PyPI server error: {response.status_code}",
                    }

                # Success - parse JSON
                response.raise_for_status()
                data = response.json()

                info = data.get("info", {})

                # Extract license from info.license field
                license_name = (info.get("license") or "").strip()

                # If empty, try to extract from classifiers
                if not license_name:
                    classifiers = info.get("classifiers", [])
                    for classifier in classifiers:
                        if classifier.startswith("License :: "):
                            # Extract license name from classifier
                            # e.g., "License :: OSI Approved :: MIT License" -> "MIT License"
                            parts = classifier.split(" :: ")
                            if len(parts) >= 3:
                                license_name = parts[-1]
                                break

                # Default to "Unknown" if still empty
                if not license_name:
                    license_name = "Unknown"

                # Extract homepage URL (prefer GitHub URLs for license detection)
                homepage_url = (info.get("home_page") or "").strip()
                license_text_url = None

                # Try project_urls with priority for source code URLs
                project_urls = info.get("project_urls") or {}
                # Priority order for finding repository URL
                url_keys = [
                    "Source code",
                    "Source Code",
                    "Source",
                    "Repository",
                    "GitHub",
                    "Homepage",
                    "Home",
                    "Issue tracker",
                ]

                # Priority order for finding license URL
                license_url_keys = [
                    "License",
                    "license",
                    "LICENSE",
                ]
                for key in license_url_keys:
                    url = project_urls.get(key, "")
                    if url:
                        license_text_url = url
                        break

                # Always try to find GitHub URL from project_urls (even if home_page exists)
                github_url = None
                for key in url_keys:
                    url = project_urls.get(key, "")
                    if url and "github.com" in url.lower():
                        github_url = url
                        break

                # Prefer GitHub URL over non-GitHub homepage
                if github_url:
                    homepage_url = github_url
                    # If no explicit license URL, generate from GitHub URL
                    if not license_text_url:
                        # Extract owner/repo from GitHub URL
                        match = re.search(r"github\.com/([^/]+)/([^/]+)", github_url)
                        if match:
                            owner = match.group(1)
                            repo = match.group(2).rstrip("/")
                            license_text_url = (
                                f"https://github.com/{owner}/{repo}/blob/main/LICENSE"
                            )
                elif not homepage_url:
                    # If no GitHub URL and no homepage, try any URL from project_urls
                    for key in url_keys:
                        url = project_urls.get(key, "")
                        if url:
                            homepage_url = url
                            break

                result: dict[str, Any] = {
                    "success": True,
                    "package_name": info.get("name", package_name),
                    "license": license_name,
                    "source": "pypi",
                }

                if "version" in info:
                    result["version"] = info["version"]

                if homepage_url:
                    result["homepage_url"] = homepage_url

                if license_text_url:
                    result["license_text_url"] = license_text_url

                return result

        except httpx.TimeoutException:
            # Timeout is transient - retry
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                time.sleep(delay)
                continue

            return {
                "success": False,
                "package_name": package_name,
                "error": "Request timeout while searching PyPI",
            }

        except httpx.NetworkError as e:
            # Network error is transient - retry
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
            # JSON decode error or other unexpected errors - NOT worth retrying
            return {
                "success": False,
                "package_name": package_name,
                "error": f"Unexpected error: {e!s}",
            }

    # Should not reach here, but just in case
    return {
        "success": False,
        "package_name": package_name,
        "error": "Max retries exceeded",
    }

"""npm registry search tool for license information."""

import time
from typing import Any

import httpx


def npm_search(package_name: str, version: str | None = None) -> dict[str, Any]:
    """
    Search npm registry for package license information.

    Args:
        package_name: Package name to search (supports scoped packages like @types/node).
        version: Optional specific version to search.

    Returns:
        Dict with search results:
            - success: bool - Whether search succeeded
            - package_name: str - Package name searched
            - license: str - License name (or "Unknown")
            - version: str - Package version (if found)
            - homepage_url: str - Homepage URL (if found)
            - source: str - Always "npm"
            - error: str - Error message (if failed)
    """
    # URL encode scoped packages (@ is fine, but / needs encoding)
    encoded_name = package_name.replace("/", "%2F")

    # Build npm registry API URL
    if version:
        url = f"https://registry.npmjs.org/{encoded_name}/{version}"
    else:
        url = f"https://registry.npmjs.org/{encoded_name}/latest"

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
                    # Try to get package metadata without version
                    url = f"https://registry.npmjs.org/{encoded_name}"
                    response = client.get(url)
                    if response.status_code == 404:
                        return {
                            "success": False,
                            "package_name": package_name,
                            "error": "Package not found on npm registry",
                        }
                    if response.status_code == 200:
                        data = response.json()
                        # Get latest version info
                        if "dist-tags" in data and "latest" in data["dist-tags"]:
                            latest_version = data["dist-tags"]["latest"]
                            if "versions" in data and latest_version in data["versions"]:
                                data = data["versions"][latest_version]

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
                        "error": f"npm registry server error: {response.status_code}",
                    }

                # Success - parse JSON
                response.raise_for_status()
                data = response.json()

                # Extract license from various formats
                license_name = _extract_npm_license(data)

                # Default to "Unknown" if empty
                if not license_name:
                    license_name = "Unknown"

                # Extract homepage URL
                homepage_url = data.get("homepage", "")

                # If no homepage, try to get repository URL
                if not homepage_url:
                    repository = data.get("repository")
                    if repository:
                        if isinstance(repository, str):
                            homepage_url = _clean_git_url(repository)
                        elif isinstance(repository, dict):
                            homepage_url = _clean_git_url(repository.get("url", ""))

                result: dict[str, Any] = {
                    "success": True,
                    "package_name": data.get("name", package_name),
                    "license": license_name,
                    "source": "npm",
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
                "error": "Request timeout while searching npm registry",
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


def _extract_npm_license(package_info: dict[str, Any]) -> str | None:
    """
    Extract license name from npm package info.

    npm package.json license field can be:
    - string: "MIT"
    - object: {"type": "MIT", "url": "..."}
    - array (deprecated): [{"type": "MIT"}, {"type": "Apache-2.0"}]

    Args:
        package_info: Package info from npm registry

    Returns:
        License name, or None if not found
    """
    # New format: license field
    license_field = package_info.get("license")
    if license_field:
        if isinstance(license_field, str):
            return license_field
        elif isinstance(license_field, dict):
            return license_field.get("type")

    # Old format: licenses array
    licenses_field = package_info.get("licenses")
    if licenses_field and isinstance(licenses_field, list) and len(licenses_field) > 0:
        first_license = licenses_field[0]
        if isinstance(first_license, dict):
            return first_license.get("type")

    return None


def _clean_git_url(url: str) -> str:
    """
    Convert Git URL to regular HTTPS URL.

    Args:
        url: Git URL (e.g., git+https://github.com/user/repo.git)

    Returns:
        Clean HTTPS URL
    """
    if not url:
        return ""

    # Remove git+ prefix
    if url.startswith("git+"):
        url = url[4:]

    # Convert git:// to https://
    if url.startswith("git://"):
        url = "https://" + url[6:]

    # Remove .git suffix
    if url.endswith(".git"):
        url = url[:-4]

    return url

"""Go module search tool for license information."""

import os
import re
import time
from typing import Any

import httpx


def go_search(module_path: str, version: str | None = None) -> dict[str, Any]:
    """
    Search for Go module license information.

    For github.com hosted modules, uses GitHub API directly.
    For other modules, attempts to extract info from pkg.go.dev.

    Args:
        module_path: Go module path (e.g., github.com/user/repo).
        version: Optional specific version to search.

    Returns:
        Dict with search results:
            - success: bool - Whether search succeeded
            - package_name: str - Module path searched
            - license: str - License name (or "Unknown")
            - version: str - Module version (if found)
            - homepage_url: str - Homepage URL (if found)
            - source: str - "go" or "github"
            - error: str - Error message (if failed)
    """
    # Extract GitHub repo from module path
    github_repo = _extract_github_repo(module_path)

    if github_repo:
        # Use GitHub API for github.com hosted modules
        return _search_github_license(module_path, github_repo, version)

    # For non-GitHub modules, return basic info with pkg.go.dev link
    return {
        "success": True,
        "package_name": module_path,
        "license": "Unknown",
        "source": "go",
        "homepage_url": f"https://pkg.go.dev/{module_path}",
    }


def _extract_github_repo(module_path: str) -> str | None:
    """
    Extract GitHub repo from Go module path.

    Args:
        module_path: Go module path (e.g., github.com/user/repo/v2)

    Returns:
        GitHub repo path (e.g., user/repo), or None if not GitHub hosted
    """
    if not module_path.startswith("github.com/"):
        return None

    # Remove github.com/ prefix
    path = module_path[11:]

    # Split by /
    parts = path.split("/")

    if len(parts) < 2:
        return None

    user = parts[0]
    repo = parts[1]

    # Remove version suffix like /v2, /v3
    if re.match(r"^v\d+$", repo):
        return None

    return f"{user}/{repo}"


def _search_github_license(
    module_path: str, github_repo: str, version: str | None
) -> dict[str, Any]:
    """
    Search GitHub API for license information.

    Args:
        module_path: Original Go module path
        github_repo: GitHub repo path (user/repo)
        version: Optional version

    Returns:
        Search result dict
    """
    url = f"https://api.github.com/repos/{github_repo}"

    # Get GitHub token from environment if available
    github_token = os.getenv("GITHUB_TOKEN")

    # Retry configuration with exponential backoff
    max_retries = 3
    base_delay = 0.5  # 500ms

    for attempt in range(max_retries):
        try:
            # Prepare headers
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if github_token:
                headers["Authorization"] = f"Bearer {github_token}"

            # Make request with 5 second timeout
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url, headers=headers)

                # Handle various HTTP status codes
                if response.status_code == 404:
                    return {
                        "success": False,
                        "package_name": module_path,
                        "error": "Repository not found on GitHub",
                    }

                if response.status_code == 403:
                    data = response.json()
                    message = data.get("message", "")
                    if "rate limit" in message.lower():
                        return {
                            "success": False,
                            "package_name": module_path,
                            "error": "GitHub API rate limit exceeded",
                        }
                    return {
                        "success": False,
                        "package_name": module_path,
                        "error": f"GitHub API forbidden (403): {message}",
                    }

                if response.status_code >= 500:
                    return {
                        "success": False,
                        "package_name": module_path,
                        "error": f"GitHub server error: {response.status_code}",
                    }

                # Success - parse JSON
                response.raise_for_status()
                data = response.json()

                # Extract license information
                license_info = data.get("license")
                license_name = "Unknown"

                if license_info:
                    license_name = license_info.get("spdx_id") or license_info.get("key", "Unknown")

                homepage_url = data.get("html_url", f"https://github.com/{github_repo}")

                result: dict[str, Any] = {
                    "success": True,
                    "package_name": module_path,
                    "license": license_name,
                    "source": "github",
                    "homepage_url": homepage_url,
                }

                if version:
                    result["version"] = version

                return result

        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                time.sleep(delay)
                continue

            return {
                "success": False,
                "package_name": module_path,
                "error": "Request timeout while searching GitHub",
            }

        except httpx.NetworkError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                time.sleep(delay)
                continue

            return {
                "success": False,
                "package_name": module_path,
                "error": f"Network error: {e!s}",
            }

        except Exception as e:
            return {
                "success": False,
                "package_name": module_path,
                "error": f"Unexpected error: {e!s}",
            }

    return {
        "success": False,
        "package_name": module_path,
        "error": "Max retries exceeded",
    }

"""GitHub search tool for license information."""

import os
import re
import time
from typing import Any

import httpx


def github_search(repo_url_or_name: str) -> dict[str, Any]:
    """
    Search GitHub for repository license information.

    Args:
        repo_url_or_name: GitHub repository URL or package name.
            Examples:
                - https://github.com/psf/requests
                - psf/requests
                - requests (will try common patterns)

    Returns:
        Dict with search results:
            - success: bool - Whether search succeeded
            - package_name: str - Package/repository name
            - license: str - License name (or "Unknown")
            - source: str - Always "github"
            - homepage_url: str - Repository URL
            - license_text_url: str - URL to license file (if found)
            - error: str - Error message (if failed)
    """
    # Extract owner/repo from URL or pattern
    owner_repo_pairs = _extract_owner_repo_patterns(repo_url_or_name)

    if not owner_repo_pairs:
        return {
            "success": False,
            "package_name": repo_url_or_name,
            "error": "Invalid GitHub URL or repository name",
        }

    # Get GitHub token from environment if available
    github_token = os.getenv("GITHUB_TOKEN")

    # Retry configuration with exponential backoff
    max_retries = 3
    base_delay = 0.5  # 500ms

    # Try each owner/repo pattern
    for owner, repo in owner_repo_pairs:
        url = f"https://api.github.com/repos/{owner}/{repo}"

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
                        # Try next pattern
                        break

                    if response.status_code == 403:
                        # Rate limit or forbidden
                        data = response.json()
                        message = data.get("message", "")
                        if "rate limit" in message.lower():
                            return {
                                "success": False,
                                "package_name": repo,
                                "error": "GitHub API rate limit exceeded",
                            }
                        return {
                            "success": False,
                            "package_name": repo,
                            "error": f"GitHub API forbidden (403): {message}",
                        }

                    if response.status_code >= 500:
                        # Server error - return immediately
                        return {
                            "success": False,
                            "package_name": repo,
                            "error": f"GitHub server error: {response.status_code}",
                        }

                    # Success - parse JSON
                    response.raise_for_status()
                    data = response.json()

                    # Extract repository name
                    repo_name = data.get("name", repo)

                    # Extract license information
                    license_info = data.get("license")
                    license_name = "Unknown"
                    license_text_url = None

                    if license_info:
                        # Prefer spdx_id, fallback to key
                        license_name = license_info.get("spdx_id") or license_info.get(
                            "key", "Unknown"
                        )

                    # Extract repository URL
                    homepage_url = data.get("html_url", f"https://github.com/{owner}/{repo}")

                    # Build license text URL (use default branch)
                    default_branch = data.get("default_branch", "main")
                    license_text_url = (
                        f"https://github.com/{owner}/{repo}/blob/{default_branch}/LICENSE"
                    )

                    result = {
                        "success": True,
                        "package_name": repo_name,
                        "license": license_name,
                        "source": "github",
                        "homepage_url": homepage_url,
                    }
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
                    "package_name": repo,
                    "error": "Request timeout while searching GitHub",
                }

            except httpx.NetworkError as e:
                # Network error is transient - retry
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    time.sleep(delay)
                    continue

                return {
                    "success": False,
                    "package_name": repo,
                    "error": f"Network error: {e!s}",
                }

            except Exception as e:
                # JSON decode error or other unexpected errors - NOT worth retrying
                return {
                    "success": False,
                    "package_name": repo,
                    "error": f"Unexpected error: {e!s}",
                }

    # All patterns failed
    return {
        "success": False,
        "package_name": repo_url_or_name,
        "error": "Repository not found on GitHub",
    }


def _extract_owner_repo_patterns(repo_url_or_name: str) -> list[tuple[str, str]]:
    """
    Extract owner/repo pairs from URL or package name.

    Tries multiple patterns:
    1. Extract from GitHub URL
    2. If already in owner/repo format, use directly
    3. Try common patterns: psf/{name}, {name}/{name}

    Args:
        repo_url_or_name: GitHub URL or package name.

    Returns:
        List of (owner, repo) tuples to try.
    """
    patterns: list[tuple[str, str]] = []

    # Pattern 1: Extract from GitHub URL
    github_url_pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(github_url_pattern, repo_url_or_name)
    if match:
        owner = match.group(1)
        repo = match.group(2).rstrip("/")
        patterns.append((owner, repo))
        return patterns

    # Pattern 2: Already in owner/repo format
    if "/" in repo_url_or_name:
        parts = repo_url_or_name.split("/", 1)
        if len(parts) == 2:
            owner, repo = parts
            patterns.append((owner.strip(), repo.strip()))
            return patterns

    # Pattern 3: Try common patterns for package names
    package_name = repo_url_or_name.strip()

    # Common Python package organizations
    common_orgs = ["psf", "python", "pypa"]
    for org in common_orgs:
        patterns.append((org, package_name))

    # Same name pattern: {name}/{name}
    patterns.append((package_name, package_name))

    return patterns

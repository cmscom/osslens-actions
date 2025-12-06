"""GitHubSource for fetching license info from GitHub API."""

import logging

import httpx

from oss_license_scan.models import LicenseResult, Package
from oss_license_scan.utils.http import http_client
from oss_license_scan.utils.security import (
    SecurityValidationError,
    mask_secret,
    validate_github_repo,
)

logger = logging.getLogger(__name__)

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"


class GitHubSource:
    """GitHub API license source.

    Fetches license information from GitHub repository API.

    Example:
        >>> source = GitHubSource(token="ghp_...")
        >>> pkg = Package(ecosystem="python", name="requests", version="2.28.0",
        ...               extra={"github_repo": "psf/requests"})
        >>> result = source.resolve(pkg)
        >>> print(result.license_spdx)  # "Apache-2.0"
    """

    def __init__(
        self,
        token: str | None = None,
    ) -> None:
        """Initialize the GitHub source.

        Args:
            token: GitHub API token for authentication (optional but recommended)
        """
        self._token = token

    @property
    def name(self) -> str:
        """Return source name."""
        return "github"

    @property
    def ecosystems(self) -> list[str] | None:
        """Return supported ecosystems (None = all)."""
        return None  # Supports all ecosystems

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """Resolve license from GitHub API.

        Requires the package to have extra.github_repo set to "owner/repo".

        Args:
            pkg: Package to resolve

        Returns:
            LicenseResult if found, None otherwise
        """
        github_repo = pkg.extra.get("github_repo") if pkg.extra else None
        if not github_repo or not isinstance(github_repo, str):
            return None

        # Validate github_repo format and check for path traversal
        try:
            if not validate_github_repo(github_repo):
                logger.debug(f"Invalid github_repo format: {mask_secret(github_repo, 8)}")
                return None
        except SecurityValidationError as e:
            logger.warning(f"Security validation failed for {pkg.name}: {e.message}")
            return None

        spdx_id, license_name = self._fetch_license(github_repo)
        if not spdx_id:
            return None

        return LicenseResult(
            source_name=self.name,
            package=pkg,
            license_spdx=spdx_id,
            raw_license=license_name,
            evidence_path=f"https://github.com/{github_repo}",
        )

    def _fetch_license(self, repo: str) -> tuple[str | None, str | None]:
        """Fetch license information from GitHub API.

        Args:
            repo: Repository in "owner/repo" format

        Returns:
            Tuple of (spdx_id, license_name) or (None, None) if not found
        """
        url = f"{GITHUB_API_URL}/repos/{repo}"

        try:
            with http_client() as client:
                # Add GitHub-specific headers
                headers = {"Accept": "application/vnd.github.v3+json"}
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"

                response = client.get(url, headers=headers)

            if response.status_code == 404:
                logger.warning(f"GitHub repository not found: {repo}")
                return None, None

            if response.status_code == 403:
                # Rate limited or authentication error
                remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
                logger.warning(f"GitHub API rate limited: {repo}, remaining: {remaining}")
                return None, None

            if response.status_code != 200:
                logger.warning(f"GitHub API error for {repo}: {response.status_code}")
                return None, None

            data = response.json()
            license_info = data.get("license")

            if not license_info:
                logger.debug(f"No license found for {repo}")
                return None, None

            spdx_id = license_info.get("spdx_id")
            license_name = license_info.get("name")

            return spdx_id, license_name

        except httpx.RequestError as e:
            logger.warning(f"GitHub API request failed for {repo}: {e}")
            return None, None

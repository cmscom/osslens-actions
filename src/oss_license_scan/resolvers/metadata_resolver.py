"""License resolver using importlib.metadata."""

import importlib.metadata
import logging
from importlib.metadata import PackageNotFoundError

from oss_license_scan.license_utils import normalize_license_name
from oss_license_scan.models import Dependency, DependencyWithLicense

logger = logging.getLogger(__name__)


def resolve_license(dependency: Dependency) -> DependencyWithLicense:
    """
    Resolve license information for a dependency using importlib.metadata.

    Args:
        dependency: Dependency object to resolve

    Returns:
        DependencyWithLicense object with license information

    Note:
        This resolver only works for packages installed in the current environment.
        If a package is not installed, license information will be None.
    """
    try:
        # Get package metadata
        metadata = importlib.metadata.metadata(dependency.name)

        # Extract license information and normalize
        raw_license = metadata.get("License")
        license_name = normalize_license_name(raw_license)
        homepage_url = metadata.get("Home-page")

        # Try to get project URLs for license text
        license_text_url = None
        project_urls = metadata.get_all("Project-URL") or []

        for url_entry in project_urls:
            # Project-URL format: "label, url"
            if "," in url_entry:
                label, url = url_entry.split(",", 1)
                label = label.strip().lower()
                url = url.strip()

                # Look for license-related URLs
                if "license" in label or "source" in label or "repository" in label:
                    license_text_url = url
                    break

        # Create DependencyWithLicense object
        # license_source は metadata から取得できた場合のみ設定
        return DependencyWithLicense(
            name=dependency.name,
            version=dependency.version,
            ecosystem=dependency.ecosystem,
            group_id=dependency.group_id,
            artifact_id=dependency.artifact_id,
            module_path=dependency.module_path,
            license=license_name if license_name else None,
            license_text_url=license_text_url,
            homepage_url=homepage_url if homepage_url else None,
            license_source="metadata" if license_name else None,
            agent_search=None,
            custom_classification=None,
        )

    except PackageNotFoundError:
        # Package not installed - return with None license info
        logger.debug(f"Package not found in environment: {dependency.name}")
        return DependencyWithLicense(
            name=dependency.name,
            version=dependency.version,
            ecosystem=dependency.ecosystem,
            group_id=dependency.group_id,
            artifact_id=dependency.artifact_id,
            module_path=dependency.module_path,
            license=None,
            license_text_url=None,
            homepage_url=None,
            license_source=None,
            agent_search=None,
            custom_classification=None,
        )


def resolve_licenses(dependencies: list[Dependency]) -> list[DependencyWithLicense]:
    """
    Resolve license information for multiple dependencies.

    Args:
        dependencies: List of Dependency objects

    Returns:
        List of DependencyWithLicense objects
    """
    return [resolve_license(dep) for dep in dependencies]

"""JSON reporter for scan results."""

from datetime import datetime
from pathlib import Path

from oss_license_scan.models import (
    CustomLicenseClassification,
    DependencyWithPolicy,
    LicenseCompatibility,
    LicenseCount,
    LLMStats,
    PolicySummary,
    ScanReport,
    ScanSummary,
)


def generate_summary(dependencies: list[DependencyWithPolicy]) -> ScanSummary:
    """
    Generate scan summary from dependencies.

    Args:
        dependencies: List of dependencies with license information

    Returns:
        ScanSummary object with aggregated statistics
    """
    total_dependencies = len(dependencies)

    # Count licenses
    license_counts: dict[str, int] = {}
    for dep in dependencies:
        license_name = dep.license if dep.license else "Unknown"
        license_counts[license_name] = license_counts.get(license_name, 0) + 1

    # Convert to LicenseCount list
    by_license = [
        LicenseCount(license=license_name, count=count)
        for license_name, count in sorted(license_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return ScanSummary(total_dependencies=total_dependencies, by_license=by_license)


def generate_policy_summary(
    dependencies: list[DependencyWithPolicy], policy_applied: bool
) -> PolicySummary:
    """
    Generate policy summary from dependencies.

    Args:
        dependencies: List of dependencies with policy decisions
        policy_applied: Whether policy was applied

    Returns:
        PolicySummary object
    """
    if not policy_applied:
        return PolicySummary(applied=False, by_status=None)

    # Count policy statuses
    status_counts: dict[str, int] = {}
    for dep in dependencies:
        if dep.policy:
            status = dep.policy.status
            status_counts[status] = status_counts.get(status, 0) + 1

    return PolicySummary(applied=True, by_status=status_counts)


def generate_compatibility_summary(
    compatibility_checks: list[LicenseCompatibility],
) -> dict[str, int]:
    """
    Generate compatibility summary from compatibility checks.

    Args:
        compatibility_checks: List of license compatibility check results

    Returns:
        Dictionary with counts by status (compatible/conditional/incompatible/unknown)
    """
    status_counts: dict[str, int] = {
        "compatible": 0,
        "conditional": 0,
        "incompatible": 0,
        "unknown": 0,
    }

    for check in compatibility_checks:
        status_counts[check.status] += 1

    return status_counts


def create_scan_report(
    project_type: str,
    dependencies: list[DependencyWithPolicy],
    policy_applied: bool = False,
    warnings: list[str] | None = None,
    llm_stats: LLMStats | None = None,
    compatibility_checks: list[LicenseCompatibility] | None = None,
    custom_classifications: dict[str, CustomLicenseClassification] | None = None,
    mode: str = "fast",
    divergent_count: int = 0,
    deep_source_stats: dict[str, int] | None = None,
) -> ScanReport:
    """
    Create a complete scan report.

    Args:
        project_type: Type of project being scanned
        dependencies: List of dependencies with license and policy information
        policy_applied: Whether policy checking was applied
        warnings: List of warning messages
        llm_stats: LLM inference statistics (optional)
        compatibility_checks: List of license compatibility check results (optional)
        custom_classifications: Custom license classification results (optional)
        mode: Resolution mode ("fast" or "deep")
        divergent_count: Number of packages with divergent licenses (deep mode)
        deep_source_stats: Per-source result counts for deep mode (optional)

    Returns:
        Complete ScanReport object
    """
    summary = generate_summary(dependencies)
    policy_summary = generate_policy_summary(dependencies, policy_applied)

    # Generate compatibility summary if checks are provided
    compatibility_summary = (
        generate_compatibility_summary(compatibility_checks) if compatibility_checks else {}
    )

    return ScanReport(
        project_type=project_type,
        generated_at=datetime.now(),
        summary=summary,
        dependencies=dependencies,
        policy_summary=policy_summary,
        warnings=warnings or [],
        llm_stats=llm_stats,
        compatibility_summary=compatibility_summary,
        custom_classifications=custom_classifications or {},
        mode=mode,
        divergent_count=divergent_count,
        deep_source_stats=deep_source_stats or {},
    )


def export_json(report: ScanReport, output_path: Path | str | None = None) -> str:
    """
    Export scan report to JSON format.

    Args:
        report: ScanReport to export
        output_path: Optional path to write JSON file. If None, returns JSON string.

    Returns:
        JSON string representation of the report
    """
    json_str = report.model_dump_json(indent=2, exclude_none=False)

    if output_path:
        path = Path(output_path)
        path.write_text(json_str, encoding="utf-8")

    return json_str


def pretty_print_json(report: ScanReport) -> None:
    """
    Pretty print scan report as JSON to stdout.

    Args:
        report: ScanReport to print
    """
    json_str = export_json(report)
    print(json_str)

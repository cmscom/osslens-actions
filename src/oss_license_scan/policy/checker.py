"""Policy checker logic."""

import logging

from oss_license_scan.models import (
    DependencyWithLicense,
    DependencyWithPolicy,
    PolicyConfig,
    PolicyDecision,
)

logger = logging.getLogger(__name__)


def apply_policy(
    dependency: DependencyWithLicense, policy_config: PolicyConfig
) -> DependencyWithPolicy:
    """
    Apply policy to a single dependency.

    Args:
        dependency: Dependency with license information
        policy_config: Policy configuration

    Returns:
        DependencyWithPolicy with policy decision attached

    Examples:
        >>> from oss_license_scan.models import PolicyConfig, PolicyRule
        >>> policy = PolicyConfig(version=1, default_action="warn", rules=[
        ...     PolicyRule(license="MIT", status="allow")
        ... ])
        >>> dep = DependencyWithLicense(name="pkg", version="1.0.0", license="MIT")
        >>> result = apply_policy(dep, policy)
        >>> result.policy.status
        'allow'
    """
    # Find matching rule
    matching_rule = None
    if dependency.license:
        for rule in policy_config.rules:
            if rule.license == dependency.license:
                matching_rule = rule
                break

    # Determine policy decision
    if matching_rule:
        # Use rule-specific status and reason
        status = matching_rule.status
        reason = matching_rule.reason
        logger.debug(
            f"Applied policy rule for {dependency.name}: {status} (license: {dependency.license})"
        )
    else:
        # Use default status
        status = policy_config.default_status
        reason = None

        # Special handling for null/unknown licenses
        if dependency.license is None or dependency.license == "Unknown":
            # Default to deny for unknown licenses if default is allow
            if policy_config.default_status == "allow":
                # Override allow with deny for unknown licenses
                status = "deny"
                reason = "License information not available"
            logger.debug(
                f"Applied default status for {dependency.name}: {status} (license unknown)"
            )
        else:
            logger.debug(
                f"Applied default status for {dependency.name}: {status} (license: {dependency.license})"
            )

    # Create policy decision
    policy_decision = PolicyDecision(status=status, reason=reason)

    # Create DependencyWithPolicy
    return DependencyWithPolicy(
        name=dependency.name,
        version=dependency.version,
        ecosystem=dependency.ecosystem,
        group_id=dependency.group_id,
        artifact_id=dependency.artifact_id,
        module_path=dependency.module_path,
        license=dependency.license,
        license_text_url=dependency.license_text_url,
        homepage_url=dependency.homepage_url,
        license_source=dependency.license_source,
        agent_search=dependency.agent_search,
        custom_classification=dependency.custom_classification,
        policy=policy_decision,
    )


def apply_policies(
    dependencies: list[DependencyWithLicense], policy_config: PolicyConfig
) -> list[DependencyWithPolicy]:
    """
    Apply policy to multiple dependencies.

    Args:
        dependencies: List of dependencies with license information
        policy_config: Policy configuration

    Returns:
        List of DependencyWithPolicy objects

    Examples:
        >>> deps = [
        ...     DependencyWithLicense(name="pkg1", version="1.0.0", license="MIT"),
        ...     DependencyWithLicense(name="pkg2", version="2.0.0", license="GPL-3.0-only"),
        ... ]
        >>> from oss_license_scan.models import PolicyConfig, PolicyRule
        >>> policy = PolicyConfig(version=1, default_action="warn", rules=[
        ...     PolicyRule(license="MIT", status="allow"),
        ...     PolicyRule(license="GPL-3.0-only", status="deny"),
        ... ])
        >>> results = apply_policies(deps, policy)
        >>> len(results)
        2
    """
    return [apply_policy(dep, policy_config) for dep in dependencies]

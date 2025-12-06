"""Policy file loader."""

import json
import logging
from pathlib import Path

from oss_license_scan.api import PolicyValidationError
from oss_license_scan.models import PolicyConfig, PolicyRule

logger = logging.getLogger(__name__)


def load_policy(policy_file: str | Path) -> PolicyConfig:
    """
    Load policy configuration from JSON file.

    Args:
        policy_file: Path to policy.json file

    Returns:
        PolicyConfig object

    Raises:
        FileNotFoundError: If policy file not found
        PolicyValidationError: If policy file is invalid

    Examples:
        >>> policy = load_policy("policy.json")
        >>> print(policy.version)
        1
    """
    path = Path(policy_file)

    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_file}")

    try:
        # Read and parse JSON
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)

        # Validate required fields
        if not isinstance(data, dict):
            raise PolicyValidationError("Policy file must be a JSON object")

        # Extract rules
        rules_data = data.get("rules", [])
        if not isinstance(rules_data, list):
            raise PolicyValidationError("'rules' must be a list")

        # Parse rules
        rules: list[PolicyRule] = []
        for rule_data in rules_data:
            if not isinstance(rule_data, dict):
                raise PolicyValidationError("Each rule must be a JSON object")

            # Required fields
            if "license" not in rule_data:
                raise PolicyValidationError("Rule missing required field: 'license'")
            if "status" not in rule_data:
                raise PolicyValidationError("Rule missing required field: 'status'")

            # Validate status
            status = rule_data["status"]
            valid_statuses = ["allow", "deny", "review"]
            if status not in valid_statuses:
                # Provide helpful message for common mistakes
                if status == "warn":
                    raise PolicyValidationError(
                        f"Invalid status 'warn'. 'warn' is not supported. "
                        f"Use 'review' instead for licenses that need manual review. "
                        f"Valid statuses: {', '.join(valid_statuses)}"
                    )
                raise PolicyValidationError(
                    f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
                )

            # Create PolicyRule
            rule = PolicyRule(
                license=rule_data["license"],
                status=status,
                reason=rule_data.get("reason"),
            )
            rules.append(rule)

        # Extract other fields with defaults
        version = data.get("version", 1)
        default_status = data.get(
            "default_action", "review"
        )  # Note: JSON uses "default_action" but model uses "default_status"

        # Validate default_status
        if default_status not in ["allow", "deny", "review"]:
            raise PolicyValidationError(
                f"Invalid default_action '{default_status}'. Must be one of: allow, deny, review"
            )

        # Create PolicyConfig
        policy_config = PolicyConfig(version=version, default_status=default_status, rules=rules)

        logger.info(f"Loaded policy with {len(rules)} rules from {policy_file}")
        return policy_config

    except json.JSONDecodeError as e:
        raise PolicyValidationError(f"Invalid JSON in policy file: {e}") from e
    except Exception as e:
        if isinstance(e, (FileNotFoundError, PolicyValidationError)):
            raise
        raise PolicyValidationError(f"Failed to load policy file: {e}") from e

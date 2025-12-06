"""Parser for requirements.txt files."""

from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from oss_license_scan.models import Dependency


def parse_requirements(content: str) -> list[Dependency]:
    """
    Parse requirements.txt content and extract dependencies.

    Args:
        content: Content of requirements.txt file

    Returns:
        List of Dependency objects

    Examples:
        >>> parse_requirements("requests==2.32.3")
        [Dependency(name='requests', version='2.32.3')]
    """
    dependencies: list[Dependency] = []
    lines = content.strip().split("\n")

    for line in lines:
        # Remove leading/trailing whitespace
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Skip git URLs and other non-standard formats (will add to warnings later)
        if line.startswith("git+") or line.startswith("http://") or line.startswith("https://"):
            continue

        try:
            # Use packaging library to parse requirement
            req = Requirement(line)

            # Extract name and version
            name = req.name
            version = None

            # Try to extract version from specifier
            if req.specifier:
                # Get the first specifier (e.g., ==2.32.3, >=2.0.0)
                specs = list(req.specifier)
                if specs:
                    # For exact version (==), use it as version
                    # For others (>=, ~=, etc.), use the specifier string
                    first_spec = specs[0]
                    if first_spec.operator == "==":
                        version = first_spec.version
                    else:
                        # Store the full specifier string for non-exact versions
                        version = str(req.specifier)

            dependencies.append(Dependency(name=name, version=version))

        except InvalidRequirement:
            # Skip invalid requirements (will be added to warnings)
            continue

    return dependencies


def parse_requirements_file(file_path: Path | str) -> list[Dependency]:
    """
    Parse a requirements.txt file.

    Args:
        file_path: Path to requirements.txt file

    Returns:
        List of Dependency objects

    Raises:
        FileNotFoundError: If the file does not exist
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Requirements file not found: {file_path}")

    content = path.read_text(encoding="utf-8")
    return parse_requirements(content)

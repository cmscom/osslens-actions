"""Command-line interface for OSS license scanning."""

import sys
from pathlib import Path
from typing import Annotated

import typer

from oss_license_scan.api import PolicyValidationError, scan_project
from oss_license_scan.llm.cache import SQLiteCacheWithTTL
from oss_license_scan.reporters.json_reporter import export_json, pretty_print_json
from oss_license_scan.reporters.markdown_reporter import export_markdown

app = typer.Typer(
    name="oss-license-scan",
    help="OSS license scanning tool with LLM integration",
    add_completion=False,
)


FORMAT_CHOICES = [
    "auto",
    "requirements",
    "pyproject",
    "pylock",
    "package-lock",
    "go-sum",
    "gemfile-lock",
    "pom",
    "gradle-lock",
]


MODE_CHOICES = ["fast", "deep"]


@app.command(name="scan")
def scan_command(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input file (lock file or dependency file)",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    format_option: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help=(
                "File format (auto-detected if not specified). "
                "Supported: requirements, pyproject, pylock, package-lock, go-sum, "
                "gemfile-lock, pom, gradle-lock"
            ),
        ),
    ] = "auto",
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Resolution mode: 'fast' (first source wins) or 'deep' (all sources, consistency check)",
        ),
    ] = "fast",
    project_type: Annotated[
        str | None,
        typer.Option(
            "--project-type",
            "-t",
            help="(Deprecated) Use --format instead",
            hidden=True,
        ),
    ] = None,
    policy: Annotated[
        Path | None,
        typer.Option(
            "--policy",
            "-p",
            help="Path to policy.json file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output JSON file path (default: stdout)",
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    markdown: Annotated[
        Path | None,
        typer.Option(
            "--markdown",
            "-M",
            help="Output Markdown report file path",
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose mode (INFO logging + license summaries for all packages)",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug logging with node input/output data (DEBUG level)",
        ),
    ] = False,
    no_llm: Annotated[
        bool,
        typer.Option(
            "--no-llm",
            help="Disable LLM integration for license inference",
        ),
    ] = False,
    no_agent: Annotated[
        bool,
        typer.Option(
            "--no-agent",
            help="Disable Agent feature for dynamic license search",
        ),
    ] = False,
    explain_license: Annotated[
        str | None,
        typer.Option(
            "--explain-license",
            "-e",
            help="Generate LLM summary for specific license (e.g., 'MIT', 'Apache-2.0')",
        ),
    ] = None,
    sources: Annotated[
        str | None,
        typer.Option(
            "--sources",
            "-s",
            help=(
                "Comma-separated list of sources in priority order. "
                "Available: local, pypi, npm_registry, go_licenses, rubygems, maven_central, github, overrides. "
                "Example: --sources 'pypi,github'"
            ),
        ),
    ] = None,
    overrides: Annotated[
        Path | None,
        typer.Option(
            "--overrides",
            "-O",
            help="Path to license_overrides.yml file for manual license overrides",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
) -> None:
    """
    Scan a project for OSS license information.

    Supported formats:
      - Python: requirements.txt, pyproject.toml, pylock.toml
      - Node.js: package-lock.json
      - Go: go.sum
      - Ruby: Gemfile.lock
      - Java: pom.xml, gradle.lockfile

    Examples:
        oss-license-scan scan pylock.toml -o report.json

        oss-license-scan scan package-lock.json -o report.json

        oss-license-scan scan go.sum -o report.json -m report.md

        oss-license-scan scan deps.toml --format pylock -o report.json
    """
    # Configure logging
    import logging

    # Handle deprecated --project-type option
    if project_type is not None:
        typer.echo(
            "Warning: --project-type is deprecated. Use --format instead.",
            err=True,
        )
        # Map old project_type to new format
        if format_option == "auto":
            format_option = project_type

    # Validate format option
    if format_option not in FORMAT_CHOICES:
        typer.echo(
            f"Error: Invalid format '{format_option}'. "
            f"Supported: {', '.join(FORMAT_CHOICES)} (exit code: 1)",
            err=True,
        )
        sys.exit(1)

    # Validate mode option
    if mode not in MODE_CHOICES:
        typer.echo(
            f"Error: Invalid mode '{mode}'. Use 'fast' or 'deep'. (exit code: 3)",
            err=True,
        )
        sys.exit(3)

    if debug:
        # DEBUG: 詳細なノード入出力データを含む
        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    elif verbose:
        # INFO: ノードの開始・完了メッセージ
        logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    else:
        # WARNING: エラーと警告のみ
        logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")

    # Parse sources option
    source_list: list[str] | None = None
    if sources:
        source_list = [s.strip() for s in sources.split(",") if s.strip()]
        if verbose or debug:
            typer.echo(f"Using custom sources: {', '.join(source_list)}", err=True)

    try:
        # Run scan
        if verbose or debug:
            typer.echo(f"Scanning {input_file}...", err=True)

        # Determine effective format for API call
        effective_format = format_option if format_option != "auto" else None

        report = scan_project(
            input_file=input_file,
            project_type=effective_format,
            policy_file=policy,
            enable_llm=not no_llm,
            enable_agent=not no_agent,
            verbose=verbose,
            explain_license=explain_license,
            license_sources=source_list,
            overrides_file=overrides,
            mode=mode,
        )

        if verbose or debug:
            typer.echo(f"Found {report.summary.total_dependencies} dependencies", err=True)

        # Output JSON
        if output:
            if verbose or debug:
                typer.echo(f"Writing JSON report to {output}...", err=True)
            export_json(report, output)
            typer.echo(f"✓ JSON report saved to {output}", err=True)
        else:
            # Print to stdout
            pretty_print_json(report)

        # Output Markdown (if requested)
        if markdown:
            if verbose or debug:
                typer.echo(f"Writing Markdown report to {markdown}...", err=True)
            export_markdown(report, markdown)
            typer.echo(f"✓ Markdown report saved to {markdown}", err=True)

        # Exit with appropriate code
        if report.policy_summary.applied:
            # Check for policy violations
            if (
                report.policy_summary.by_status
                and report.policy_summary.by_status.get("deny", 0) > 0
            ):
                # FR-003: Display violated package details
                denied_packages = [
                    dep for dep in report.dependencies if dep.policy and dep.policy.status == "deny"
                ]
                typer.echo(
                    f"⚠ Policy violations detected: "
                    f"{report.policy_summary.by_status['deny']} denied package(s)",
                    err=True,
                )
                for dep in denied_packages:
                    typer.echo(f"  - {dep.name}: {dep.license} (deny)", err=True)
                # FR-002: Display exit code
                typer.echo("Exit code: 2", err=True)
                sys.exit(2)  # Exit code 2 for policy violations

        # Check for divergent packages in deep mode (T069)
        if report.mode == "deep" and report.divergent_count > 0:
            typer.echo(
                f"⚠ License divergence detected: {report.divergent_count} package(s) have inconsistent licenses",
                err=True,
            )
            typer.echo("Exit code: 10", err=True)
            sys.exit(10)  # Exit code 10 for divergent packages

        # FR-002: Display exit code on success
        typer.echo("✓ Scan completed successfully (exit code: 0)", err=True)
        sys.exit(0)  # Success

    except FileNotFoundError as e:
        typer.echo(f"Error: {e} (exit code: 1)", err=True)
        sys.exit(1)

    except PolicyValidationError as e:
        typer.echo(f"Policy Error: {e} (exit code: 1)", err=True)
        sys.exit(1)

    except ValueError as e:
        typer.echo(f"Error: {e} (exit code: 1)", err=True)
        sys.exit(1)

    except Exception as e:
        typer.echo(f"Unexpected error: {e} (exit code: 1)", err=True)
        if verbose or debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@app.command(name="clear-cache")
def clear_cache_command(
    database_path: Annotated[
        str,
        typer.Option(
            "--database-path",
            "-d",
            help="Path to cache database file",
        ),
    ] = ".cache/llm_cache.db",
) -> None:
    """Clear all LLM cache entries."""
    try:
        cache = SQLiteCacheWithTTL(database_path=database_path)
        cache.clear()
        typer.echo(f"✓ All cache entries cleared from {database_path}")
        sys.exit(0)
    except Exception as e:
        typer.echo(f"Error clearing cache: {e}", err=True)
        sys.exit(1)


@app.command(name="clear-package-cache")
def clear_package_cache_command(
    package_name: Annotated[
        str,
        typer.Argument(help="Package name to clear cache for"),
    ],
    version: Annotated[
        str,
        typer.Argument(help="Package version to clear cache for"),
    ],
    database_path: Annotated[
        str,
        typer.Option(
            "--database-path",
            "-d",
            help="Path to cache database file",
        ),
    ] = ".cache/llm_cache.db",
) -> None:
    """Clear LLM cache for a specific package version."""
    try:
        cache = SQLiteCacheWithTTL(database_path=database_path)
        deleted_count = cache.clear_package_cache(package_name, version)
        typer.echo(f"✓ Cleared {deleted_count} cache entries for {package_name}=={version}")
        sys.exit(0)
    except Exception as e:
        typer.echo(f"Error clearing package cache: {e}", err=True)
        sys.exit(1)


@app.command(name="cleanup-cache")
def cleanup_cache_command(
    database_path: Annotated[
        str,
        typer.Option(
            "--database-path",
            "-d",
            help="Path to cache database file",
        ),
    ] = ".cache/llm_cache.db",
) -> None:
    """Remove expired LLM cache entries."""
    try:
        cache = SQLiteCacheWithTTL(database_path=database_path)
        deleted_count = cache.cleanup_expired_cache()
        typer.echo(f"✓ Cleaned up {deleted_count} expired cache entries")
        sys.exit(0)
    except Exception as e:
        typer.echo(f"Error cleaning up cache: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    app()

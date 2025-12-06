"""LicenseSource implementations for multi-source license resolution."""

from oss_license_scan.sources.adapter import ResolverAdapter
from oss_license_scan.sources.base import LicenseSource
from oss_license_scan.sources.go_source import GoLicensesSource
from oss_license_scan.sources.maven_source import MavenCentralSource
from oss_license_scan.sources.npm_source import NpmRegistrySource
from oss_license_scan.sources.pypi_source import PyPISource
from oss_license_scan.sources.registry import SourceRegistry
from oss_license_scan.sources.rubygems_source import RubyGemsSource

__all__ = [
    "LicenseSource",
    "SourceRegistry",
    "ResolverAdapter",
    "PyPISource",
    "NpmRegistrySource",
    "GoLicensesSource",
    "RubyGemsSource",
    "MavenCentralSource",
]

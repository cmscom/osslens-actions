"""License resolvers package."""

from oss_license_scan.resolvers.base import BaseLicenseResolver
from oss_license_scan.resolvers.go_resolver import GoLicenseResolver
from oss_license_scan.resolvers.maven_resolver import MavenLicenseResolver
from oss_license_scan.resolvers.npm_resolver import NpmLicenseResolver
from oss_license_scan.resolvers.registry import ResolverRegistry
from oss_license_scan.resolvers.rubygems_resolver import RubyGemsLicenseResolver

# Register resolvers
ResolverRegistry.register(NpmLicenseResolver)
ResolverRegistry.register(GoLicenseResolver)
ResolverRegistry.register(RubyGemsLicenseResolver)
ResolverRegistry.register(MavenLicenseResolver)

__all__ = [
    "BaseLicenseResolver",
    "GoLicenseResolver",
    "MavenLicenseResolver",
    "NpmLicenseResolver",
    "ResolverRegistry",
    "RubyGemsLicenseResolver",
]

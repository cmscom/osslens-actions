"""Lock file parsers package."""

from oss_license_scan.parsers.base import BaseLockFileParser, ParseError
from oss_license_scan.parsers.gemfile_lock_parser import GemfileLockParser
from oss_license_scan.parsers.go_sum_parser import GoSumParser
from oss_license_scan.parsers.gradle_lockfile_parser import GradleLockfileParser
from oss_license_scan.parsers.package_lock_parser import PackageLockJsonParser
from oss_license_scan.parsers.pom_xml_parser import PomXmlParser
from oss_license_scan.parsers.pylock_parser import PylockTomlParser
from oss_license_scan.parsers.pyproject_parser import PyprojectTomlParser
from oss_license_scan.parsers.registry import ParserRegistry

# Register all parsers
ParserRegistry.register(PylockTomlParser)
ParserRegistry.register(PyprojectTomlParser)
ParserRegistry.register(PackageLockJsonParser)
ParserRegistry.register(GoSumParser)
ParserRegistry.register(GemfileLockParser)
ParserRegistry.register(PomXmlParser)
ParserRegistry.register(GradleLockfileParser)

__all__ = [
    "BaseLockFileParser",
    "ParseError",
    "ParserRegistry",
    "PylockTomlParser",
    "PyprojectTomlParser",
    "PackageLockJsonParser",
    "GoSumParser",
    "GemfileLockParser",
    "PomXmlParser",
    "GradleLockfileParser",
]

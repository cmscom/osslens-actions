"""LLM cache with TTL support using SQLite."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from langchain_core.caches import BaseCache
from langchain_core.outputs import Generation
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base

from oss_license_scan.utils.security import escape_like_pattern

Base = declarative_base()


class LLMCacheEntry(Base):
    """
    LLM cache SQLite table.

    Columns:
        prompt: Prompt string (Primary Key)
        llm: LLM configuration serialized (Primary Key)
        idx: Index for multiple generations (Primary Key)
        response: LLM response JSON string
        created_at: Created timestamp
        expires_at: Expiration timestamp (TTL management)
    """

    __tablename__ = "llm_cache_with_ttl"

    prompt = Column(String, primary_key=True)
    llm = Column(String, primary_key=True)
    idx = Column(Integer, primary_key=True, default=0)
    response = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class AgentCacheEntry(Base):
    """
    Agent tool call cache SQLite table.

    Columns:
        cache_key: Unique cache key (tool_name:params_hash) (Primary Key)
        tool_name: Tool name (pypi_search, github_search, spdx_search)
        input_params: JSON serialized input parameters
        output_result: JSON serialized output result
        created_at: Created timestamp
        expires_at: Expiration timestamp (TTL management)
    """

    __tablename__ = "agent_cache"

    cache_key = Column(String, primary_key=True)
    tool_name = Column(String, nullable=False, index=True)
    input_params = Column(Text, nullable=False)
    output_result = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class SQLiteCacheWithTTL(BaseCache):
    """
    TTL-enabled SQLite cache.

    Extends LangChain's BaseCache to provide TTL functionality.
    """

    def __init__(self, database_path: str = ".cache/llm_cache.db", ttl_seconds: int = 604800):
        """
        Initialize SQLite cache with TTL.

        Args:
            database_path: Path to SQLite database file.
            ttl_seconds: Cache TTL in seconds (default: 604800 = 7 days).
        """
        self.database_path = database_path
        self.ttl_seconds = ttl_seconds  # Store as integer for inspection

        # Create database directory if it doesn't exist
        if database_path != ":memory:":
            db_dir = os.path.dirname(database_path)
            if db_dir and not os.path.exists(db_dir):
                Path(db_dir).mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.ttl = timedelta(seconds=ttl_seconds)

    def lookup(self, prompt: str, llm_string: str) -> list[Generation] | None:  # type: ignore[override]
        """
        Look up cache entry (excluding expired entries).

        Args:
            prompt: Prompt string.
            llm_string: LLM configuration serialized.

        Returns:
            List of generations if cache hit, None if cache miss.
        """
        with Session(self.engine) as session:
            rows = (
                session.query(LLMCacheEntry)
                .filter(
                    LLMCacheEntry.prompt == prompt,
                    LLMCacheEntry.llm == llm_string,
                    LLMCacheEntry.expires_at > datetime.now(UTC),  # TTL check
                )
                .order_by(LLMCacheEntry.idx)
                .all()
            )

            if not rows:
                return None

            return [Generation(text=str(row.response)) for row in rows]

    def update(self, prompt: str, llm_string: str, return_val: list[Generation]) -> None:  # type: ignore[override]
        """
        Save to cache (automatically set expires_at).

        Args:
            prompt: Prompt string.
            llm_string: LLM configuration serialized.
            return_val: LLM response (list of generations).
        """
        with Session(self.engine) as session:
            for idx, generation in enumerate(return_val):
                expires_at = datetime.now(UTC) + self.ttl
                cache_entry = LLMCacheEntry(
                    prompt=prompt,
                    llm=llm_string,
                    idx=idx,
                    response=generation.text,
                    created_at=datetime.now(UTC),
                    expires_at=expires_at,
                )
                session.merge(cache_entry)
            session.commit()

    def clear(self, **kwargs: object) -> None:
        """
        Clear all cache entries.

        Args:
            **kwargs: Additional arguments (unused).
        """
        with Session(self.engine) as session:
            session.query(LLMCacheEntry).delete()
            session.commit()

    def cleanup_expired_cache(self) -> int:
        """
        Delete expired cache entries.

        Returns:
            Number of deleted entries.
        """
        with Session(self.engine) as session:
            deleted_count = (
                session.query(LLMCacheEntry)
                .filter(LLMCacheEntry.expires_at <= datetime.now(UTC))
                .delete()
            )
            session.commit()
            return deleted_count

    def clear_package_cache(self, package_name: str, version: str) -> int:
        """
        Delete cache for specific package.

        Args:
            package_name: Package name.
            version: Version.

        Returns:
            Number of deleted entries.
        """
        # Escape special characters to prevent SQL injection via LIKE pattern
        escaped_name = escape_like_pattern(package_name)
        escaped_version = escape_like_pattern(version)

        # Match prompts containing the package and version
        package_pattern = f"%{escaped_name}%{escaped_version}%"

        with Session(self.engine) as session:
            deleted_count = (
                session.query(LLMCacheEntry)
                .filter(LLMCacheEntry.prompt.like(package_pattern, escape="\\"))
                .delete(synchronize_session=False)
            )
            session.commit()
            return deleted_count

    def get_agent_cache(
        self, tool_name: str, input_params: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Get cached Agent tool call result.

        Args:
            tool_name: Tool name (pypi_search, github_search, spdx_search).
            input_params: Input parameters dict.

        Returns:
            Cached result dict if hit, None if miss.
        """
        import hashlib

        # Generate cache key from tool name and params
        params_str = json.dumps(input_params, sort_keys=True)
        params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]
        cache_key = f"{tool_name}:{params_hash}"

        with Session(self.engine) as session:
            entry = (
                session.query(AgentCacheEntry)
                .filter(
                    AgentCacheEntry.cache_key == cache_key,
                    AgentCacheEntry.expires_at > datetime.now(UTC),  # TTL check
                )
                .first()
            )

            if not entry:
                return None

            return json.loads(entry.output_result)  # type: ignore[arg-type]

    def set_agent_cache(
        self, tool_name: str, input_params: dict[str, Any], output_result: dict[str, Any]
    ) -> None:
        """
        Save Agent tool call result to cache.

        Args:
            tool_name: Tool name (pypi_search, github_search, spdx_search).
            input_params: Input parameters dict.
            output_result: Output result dict.
        """
        import hashlib

        # Generate cache key from tool name and params
        params_str = json.dumps(input_params, sort_keys=True)
        params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]
        cache_key = f"{tool_name}:{params_hash}"

        with Session(self.engine) as session:
            expires_at = datetime.now(UTC) + self.ttl
            cache_entry = AgentCacheEntry(
                cache_key=cache_key,
                tool_name=tool_name,
                input_params=params_str,
                output_result=json.dumps(output_result),
                created_at=datetime.now(UTC),
                expires_at=expires_at,
            )
            session.merge(cache_entry)
            session.commit()

    def clear_agent_cache(self) -> int:
        """
        Clear all Agent cache entries.

        Returns:
            Number of deleted entries.
        """
        with Session(self.engine) as session:
            deleted_count = session.query(AgentCacheEntry).delete()
            session.commit()
            return deleted_count

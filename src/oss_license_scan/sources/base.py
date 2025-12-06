"""LicenseSource protocol definition and base classes."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

import httpx

from oss_license_scan.models import LicenseResult, Package
from oss_license_scan.utils.http import HttpClientConfig, http_client

logger = logging.getLogger(__name__)


@runtime_checkable
class LicenseSource(Protocol):
    """ライセンス情報ソースのプロトコル。

    各ライセンス情報取得元（PyPI、npm registry、GitHub等）は
    このプロトコルを実装する。

    Attributes:
        name: ソースの一意識別子（例: "pypi", "npm_registry", "local"）
        ecosystems: 対応エコシステムのリスト。Noneは全エコシステム対応。

    Example:
        >>> class PyPISource:
        ...     @property
        ...     def name(self) -> str:
        ...         return "pypi"
        ...
        ...     @property
        ...     def ecosystems(self) -> list[str] | None:
        ...         return ["python"]
        ...
        ...     def resolve(self, pkg: Package) -> LicenseResult | None:
        ...         # PyPI APIからライセンス情報を取得
        ...         ...
    """

    @property
    def name(self) -> str:
        """ソースの一意識別子。

        Returns:
            str: ソース名（例: "pypi", "npm_registry", "local"）
        """
        ...

    @property
    def ecosystems(self) -> list[str] | None:
        """対応エコシステムのリスト。

        Returns:
            list[str]: 対応エコシステム（例: ["python"]）
            None: 全エコシステム対応（例: local, github, overrides）
        """
        ...

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """パッケージのライセンス情報を解決する。

        Args:
            pkg: 対象パッケージ

        Returns:
            LicenseResult: 取得成功時
            None: 取得失敗時（次のソースにフォールバック）

        Raises:
            なし（例外はNone返却でハンドリング）
        """
        ...


class HttpLicenseSourceBase(ABC):
    """HTTP APIベースのライセンスソースの基底クラス。

    HTTP APIからライセンス情報を取得するソースの共通機能を提供:
    - HTTPクライアント管理
    - 共通エラーハンドリングとログ出力
    - 標準化されたレスポンス処理

    サブクラスは以下を実装する必要があります:
    - name: ソース識別子
    - ecosystems: 対応エコシステム
    - _build_url: API用URL構築
    - _parse_response: レスポンスパースロジック

    Example:
        >>> class MySource(HttpLicenseSourceBase):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_source"
        ...
        ...     @property
        ...     def ecosystems(self) -> list[str] | None:
        ...         return ["python"]
        ...
        ...     def _build_url(self, pkg: Package) -> str | None:
        ...         return f"https://api.example.com/{pkg.name}"
        ...
        ...     def _parse_response(self, data, pkg):
        ...         license_name = data.get("license")
        ...         return self._create_result(pkg, license_name, license_name)
    """

    def __init__(
        self,
        base_url: str,
        http_config: HttpClientConfig | None = None,
    ) -> None:
        """HTTPライセンスソースを初期化する。

        Args:
            base_url: APIのベースURL
            http_config: HTTPクライアント設定（オプション）
        """
        self._base_url = base_url
        self._http_config = http_config or HttpClientConfig()

    @property
    def base_url(self) -> str:
        """APIのベースURLを返す。"""
        return self._base_url

    @property
    @abstractmethod
    def name(self) -> str:
        """ソース名を返す（例: 'pypi', 'npm', 'github'）。"""
        ...

    @property
    @abstractmethod
    def ecosystems(self) -> list[str] | None:
        """対応エコシステムを返す。Noneは全エコシステム対応。"""
        ...

    def resolve(self, pkg: Package) -> LicenseResult | None:
        """パッケージのライセンス情報を解決する。

        共通のHTTPリクエスト/レスポンスフローを処理:
        1. _build_urlでURLを構築
        2. エラーハンドリング付きでHTTPリクエストを実行
        3. _parse_responseでレスポンスをパース

        Args:
            pkg: 対象パッケージ

        Returns:
            LicenseResult: 取得成功時
            None: 取得失敗時
        """
        url = self._build_url(pkg)
        if not url:
            return None

        try:
            response_data = self._fetch(url, pkg)
            if response_data is None:
                return None

            return self._parse_response(response_data, pkg)

        except httpx.RequestError as e:
            logger.warning(f"HTTPリクエスト失敗 {pkg.name}: {e}")
            return None

    def _fetch(
        self,
        url: str,
        pkg: Package,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | str | None:
        """URLからデータを取得する。

        Args:
            url: 取得先URL
            pkg: 解決対象パッケージ（ログ用）
            headers: 追加ヘッダー（オプション）

        Returns:
            レスポンスデータ（JSONはdict、テキストはstr）、エラー時はNone
        """
        try:
            with http_client(self._http_config) as client:
                response = client.get(url, headers=headers)

                if response.status_code != 200:
                    # フォールバックURLがあれば試行
                    fallback_url = self._get_fallback_url(pkg)
                    if fallback_url and fallback_url != url:
                        response = client.get(fallback_url, headers=headers)

                if response.status_code != 200:
                    logger.debug(f"{self.name} returned {response.status_code} for {pkg.name}")
                    return None

                # Content-Typeに基づいてレスポンス形式を判定
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                else:
                    return response.text

        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch {self.name} info for {pkg.name}: {e}")
            return None

    @abstractmethod
    def _build_url(self, pkg: Package) -> str | None:
        """パッケージ情報取得用のURLを構築する。

        Args:
            pkg: URL構築対象パッケージ

        Returns:
            URL文字列、構築不可の場合はNone
        """
        ...

    def _get_fallback_url(self, pkg: Package) -> str | None:
        """プライマリURLが失敗した場合のフォールバックURLを取得する。

        バージョンなしURLなどのフォールバックを提供するためにオーバーライド。

        Args:
            pkg: フォールバックURL構築対象パッケージ

        Returns:
            フォールバックURL文字列、利用不可の場合はNone
        """
        return None

    @abstractmethod
    def _parse_response(self, data: dict[str, Any] | str, pkg: Package) -> LicenseResult | None:
        """APIレスポンスをパースしてライセンス情報を抽出する。

        Args:
            data: レスポンスデータ（JSONはdict、テキストはstr）
            pkg: 解決対象パッケージ

        Returns:
            LicenseResult: ライセンス発見時
            None: ライセンス未発見時
        """
        ...

    def _create_result(
        self,
        pkg: Package,
        license_spdx: str | None,
        raw_license: str | None,
        confidence: float = 1.0,
        evidence_path: str | None = None,
    ) -> LicenseResult | None:
        """共通フィールドを持つLicenseResultを作成する。

        一貫したLicenseResultオブジェクトを作成するヘルパーメソッド。

        Args:
            pkg: 解決対象パッケージ
            license_spdx: SPDXライセンス識別子
            raw_license: ソースからの生のライセンス文字列
            confidence: 信頼度スコア（0.0-1.0）
            evidence_path: ライセンス証拠のURLまたはパス

        Returns:
            LicenseResult: license_spdxまたはraw_licenseが提供された場合
            None: 両方ともNoneの場合
        """
        if not license_spdx and not raw_license:
            return None

        return LicenseResult(
            source_name=self.name,
            package=pkg,
            license_spdx=license_spdx,
            raw_license=raw_license,
            confidence=confidence,
            evidence_path=evidence_path,
        )

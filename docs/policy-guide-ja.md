# Policy Guide

> ライセンスポリシーチェックの設定方法と、policy.jsonファイルの構造を詳しく説明します。
>
> **Note**: ポリシーチェックは、Python/Node.js/Go/Ruby/Javaなど、すべてのサポート対象フォーマットで使用できます。

## 目次

- [ポリシーチェック概要](#ポリシーチェック概要)
- [policy.jsonの構造](#policyjsonの構造)
- [ルール設定](#ルール設定)
- [実例解説](#実例解説)
- [ベストプラクティス](#ベストプラクティス)
- [カスタマイズ方法](#カスタマイズ方法)

## ポリシーチェック概要

### ライセンスポリシーとは

ライセンスポリシーは、組織で使用を許可・禁止するOSSライセンスを定義したものです。

### なぜポリシーが必要か

- **法的リスク管理**: コピーレフトライセンスの混入を防止
- **コンプライアンス**: 企業ポリシーへの準拠
- **自動化**: CI/CDで自動チェック

## policy.jsonの構造

### 基本構造

```json
{
  "version": 1,
  "default_status": "review",
  "rules": [
    {
      "license": "MIT",
      "status": "allow",
      "reason": "Permissive license suitable for commercial use"
    }
  ]
}
```

### フィールド説明

- **version**: ポリシースキーマのバージョン（現在は`1`のみ）
- **default_status**: ルールに定義されていないライセンスのデフォルト動作
  - `allow`: 使用を許可
  - `review`: レビューが必要
  - `deny`: 使用を禁止
- **rules**: ライセンスごとのルール配列

## ルール設定

### ルールの構造

```json
{
  "license": "MIT",
  "status": "allow",
  "reason": "Permissive license suitable for commercial use"
}
```

### フィールド

- **license**: ライセンス名（SPDX識別子を推奨）
  - 例: `MIT`, `Apache-2.0`, `GPL-3.0-only`
- **status**: ステータス
  - `allow`: 使用を許可
  - `review`: レビューが必要（警告）
  - `deny`: 使用を禁止（ビルド失敗）
- **reason**: 理由の説明（任意だが推奨）

### SPDX識別子

正確なライセンス名は[SPDX License List](https://spdx.org/licenses/)を参照：

- ✅ 正: `GPL-3.0-only`, `Apache-2.0`
- ❌ 誤: `GPL-3.0`, `Apache 2.0`

## 実例解説

### examples/policy.json

```json
{
  "version": 1,
  "default_status": "review",
  "rules": [
    {
      "license": "MIT",
      "status": "allow",
      "reason": "Permissive license suitable for commercial use"
    },
    {
      "license": "Apache-2.0",
      "status": "allow",
      "reason": "Permissive license with patent grant, safe for enterprise"
    },
    {
      "license": "BSD-3-Clause",
      "status": "allow",
      "reason": "Permissive BSD license"
    },
    {
      "license": "ISC",
      "status": "allow",
      "reason": "Simplified permissive license"
    },
    {
      "license": "GPL-3.0-only",
      "status": "deny",
      "reason": "Strong copyleft license incompatible with proprietary software"
    },
    {
      "license": "GPL-2.0-only",
      "status": "deny",
      "reason": "Copyleft license with distribution restrictions"
    },
    {
      "license": "AGPL-3.0-only",
      "status": "deny",
      "reason": "Network copyleft license with strict requirements"
    },
    {
      "license": "LGPL-3.0-only",
      "status": "review",
      "reason": "Weak copyleft - requires legal review for linking"
    },
    {
      "license": "MPL-2.0",
      "status": "review",
      "reason": "File-level copyleft - requires review"
    },
    {
      "license": "Unknown",
      "status": "deny",
      "reason": "License must be explicitly identified before use"
    }
  ]
}
```

### 分類の説明

#### allow（許可）

- **MIT**: 最も寛容なライセンス、商用利用可
- **Apache-2.0**: 特許権付与条項あり、エンタープライズ向け
- **BSD-3-Clause**: BSDライセンス、商用利用可
- **ISC**: MIT類似のシンプルなライセンス

#### deny（禁止）

- **GPL-3.0-only**: 強いコピーレフト、プロプライエタリソフトと非互換
- **GPL-2.0-only**: コピーレフト、配布制限あり
- **AGPL-3.0-only**: ネットワークコピーレフト、SaaS提供時も要注意
- **Unknown**: ライセンス不明は使用禁止

#### review（要レビュー）

- **LGPL-3.0-only**: 弱いコピーレフト、リンク方法に注意
- **MPL-2.0**: ファイルレベルコピーレフト、要確認
- **その他（default_status）**: ルールにないライセンスは要レビュー

## ベストプラクティス

### 組織ごとのポリシー例

#### スタートアップ（寛容）

```json
{
  "version": 1,
  "default_status": "review",
  "rules": [
    {"license": "MIT", "status": "allow", "reason": "Permissive"},
    {"license": "Apache-2.0", "status": "allow", "reason": "Permissive"},
    {"license": "GPL-3.0-only", "status": "deny", "reason": "Copyleft"},
    {"license": "Unknown", "status": "deny", "reason": "Must identify"}
  ]
}
```

#### エンタープライズ（厳格）

```json
{
  "version": 1,
  "default_status": "deny",
  "rules": [
    {"license": "MIT", "status": "allow", "reason": "Pre-approved"},
    {"license": "Apache-2.0", "status": "allow", "reason": "Pre-approved"},
    {"license": "BSD-3-Clause", "status": "allow", "reason": "Pre-approved"},
    {"license": "LGPL-3.0-only", "status": "review", "reason": "Requires legal"},
    {"license": "Unknown", "status": "deny", "reason": "Must identify"}
  ]
}
```

### default_statusの選び方

- **allow**: 内部ツール、プロトタイプ（リスク高）
- **review**: スタートアップ、中小企業（推奨）
- **deny**: エンタープライズ、規制業界（最も安全）

### Unknownの扱い

ライセンス不明パッケージは必ず`deny`に設定：

```json
{
  "license": "Unknown",
  "status": "deny",
  "reason": "License must be explicitly identified before use"
}
```

## カスタマイズ方法

### 自分のプロジェクト向けに調整

1. **examples/policy.jsonをコピー**

```bash
cp examples/policy.json my-policy.json
```

2. **組織のポリシーに合わせて編集**

```json
{
  "version": 1,
  "default_status": "review",
  "rules": [
    // 許可するライセンスを追加
    {"license": "MIT", "status": "allow", "reason": "組織承認済み"},
    // 禁止するライセンスを追加
    {"license": "AGPL-3.0-only", "status": "deny", "reason": "SaaS非互換"}
  ]
}
```

3. **ポリシーを適用してスキャン**

```bash
# Python
oss-license-scan scan requirements.txt -p my-policy.json -o report.json

# Node.js
oss-license-scan scan package-lock.json -p my-policy.json -o report.json

# その他（Go, Ruby, Java）も同様に使用可能
```

### ライセンス互換性の考慮

ライセンスの互換性マトリクス：

| 使用ライセンス | MIT | Apache-2.0 | GPL-3.0 | AGPL-3.0 |
|---------------|-----|------------|---------|----------|
| MIT           | ✅  | ✅         | ⚠️      | ⚠️       |
| Apache-2.0    | ✅  | ✅         | ⚠️      | ⚠️       |
| GPL-3.0       | ✅  | ✅         | ✅      | ⚠️       |
| AGPL-3.0      | ✅  | ✅         | ✅      | ✅       |

- ✅: 互換性あり
- ⚠️: 条件付き互換（要確認）

### 段階的なポリシー適用

既存プロジェクトへの導入：

1. **Phase 1**: ポリシーなしでスキャン、現状把握
2. **Phase 2**: reviewルールのみ設定、警告を確認
3. **Phase 3**: denyルール追加、CI/CD統合

```bash
# Phase 1: 現状把握（対象ファイルはプロジェクトに応じて指定）
oss-license-scan scan requirements.txt -o baseline.json     # Python
oss-license-scan scan package-lock.json -o baseline.json    # Node.js
oss-license-scan scan go.sum -o baseline.json               # Go

# Phase 2: review警告
oss-license-scan scan requirements.txt -p policy-review-only.json

# Phase 3: deny適用
oss-license-scan scan requirements.txt -p policy-strict.json
```

## 関連ドキュメント

- [Reference Guide](./reference.md): 終了コードの詳細
- [CI/CD Integration](./ci-cd-integration.md): ポリシー違反時のビルド失敗
- [SPDX License List](https://spdx.org/licenses/): 正確なライセンス名

---

最終更新: 2025-11-27

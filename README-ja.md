# osslens-actions

GitHub ActionsでOSSライセンスをスキャンするためのAction。

## プロダクトの状況

- バージョン: v0.1.0 (初期リリース)
- 開発ステータス: アルファ版
- 動作保証: なし（自己責任での利用し、フィードバック待ち）
- 利用料: 無料（将来的に有料プラン）

## 使い方

### 基本的なスキャン

```yaml
- name: Scan licenses
  uses: cmscom/osslens-actions@v0.1.0
  with:
    file: requirements.txt
```

### レポート出力付きスキャン

```yaml
- name: Scan licenses with reports
  id: scan
  uses: cmscom/osslens-actions@v0.1.0
  with:
    file: requirements.txt
    output: license-report.json
    markdown: license-report.md

- name: Show results
  run: |
    echo "Packages: ${{ steps.scan.outputs.packages-count }}"
    echo "Violations: ${{ steps.scan.outputs.violations-count }}"
```

### ポリシーチェック付きスキャン

```yaml
- name: Scan with policy
  id: scan
  uses: cmscom/osslens-actions@v0.1.0
  with:
    file: requirements.txt
    policy: policy.json
    output: report.json

- name: Fail on violations
  if: steps.scan.outputs.violations-count != '0'
  run: exit 1
```

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `file` | Yes | - | スキャン対象の依存関係ファイル |
| `output` | No | - | JSON出力ファイルパス |
| `markdown` | No | - | Markdownレポートファイルパス |
| `policy` | No | - | ポリシー定義ファイルパス |
| `format` | No | auto | ファイル形式（auto, requirements, pylock等） |
| `verbose` | No | false | 詳細ログ出力 |
| `debug` | No | false | デバッグモード |

## 出力パラメータ

| パラメータ | 説明 |
|-----------|------|
| `result` | スキャン結果（success/failure） |
| `packages-count` | スキャンされたパッケージ数 |
| `violations-count` | ポリシー違反数 |
| `report-path` | 生成されたレポートのパス |

## スキャン結果の確認とダウンロード

上記のスキャン手順で `markdown` / `output` を生成済みである前提で、結果を表示・ダウンロードする方法を説明します。

### Job Summary に表示する

`$GITHUB_STEP_SUMMARY` を使用すると、ワークフローのサマリーページにMarkdownレポートを直接表示できます。GitHub Actions の実行結果ページで、すぐに結果を確認できます。

```yaml
- name: Display results in Job Summary
  run: |
    echo "## 📋 License Scan Results" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "- **Packages scanned**: ${{ steps.scan.outputs.packages-count }}" >> $GITHUB_STEP_SUMMARY
    echo "- **Violations found**: ${{ steps.scan.outputs.violations-count }}" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    cat license-report.md >> $GITHUB_STEP_SUMMARY
```

**確認場所**: GitHub → Actions → ワークフロー実行 → Summary タブ

### Artifacts としてダウンロードする

`actions/upload-artifact` を使用すると、レポートファイルをZIP形式でダウンロードできます。

```yaml
- name: Upload reports as artifact
  uses: actions/upload-artifact@v4
  with:
    name: license-reports
    path: |
      license-report.json
      license-report.md
    retention-days: 30  # 保存期間（省略時はリポジトリ設定に従う）
```

**ダウンロード場所**: GitHub → Actions → ワークフロー実行 → Artifacts セクション

### 両方を組み合わせた完全な例

```yaml
name: License Scan

on:
  push:
    branches: [main]
  pull_request:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Scan licenses
        id: scan
        uses: cmscom/osslens-actions@v0.1.0
        with:
          file: requirements.txt
          policy: policy.json
          output: license-report.json
          markdown: license-report.md
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      # Job Summary に結果を表示
      - name: Display results in Job Summary
        run: |
          echo "## 📋 License Scan Results" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Item | Value |" >> $GITHUB_STEP_SUMMARY
          echo "|------|-------|" >> $GITHUB_STEP_SUMMARY
          echo "| Packages | ${{ steps.scan.outputs.packages-count }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Violations | ${{ steps.scan.outputs.violations-count }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Result | ${{ steps.scan.outputs.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### Detailed Report" >> $GITHUB_STEP_SUMMARY
          cat license-report.md >> $GITHUB_STEP_SUMMARY

      # Artifacts としてアップロード
      - name: Upload reports
        uses: actions/upload-artifact@v4
        with:
          name: license-reports
          path: |
            license-report.json
            license-report.md

      # ポリシー違反があれば失敗
      - name: Check for violations
        if: steps.scan.outputs.violations-count != '0'
        run: |
          echo "::error::Found ${{ steps.scan.outputs.violations-count }} license violations"
          exit 1
```

## サポートされるファイル形式

- Python: `requirements.txt`, `pylock.toml`
- Node.js: `package-lock.json`
- Go: `go.sum`
- Ruby: `Gemfile.lock`
- Java: `pom.xml`

## シークレットの設定

OpenAI APIキーなどのシークレット情報は、GitHub Secretsを使用して安全に渡すことができます。

### 1. GitHub Secretsの設定

リポジトリの **Settings** → **Secrets and variables** → **Actions** から以下のシークレットを設定してください：

| シークレット名 | 説明 |
|---------------|------|
| `OPENAI_API_KEY` | OpenAI APIキー |
| `ANTHROPIC_API_KEY` | Anthropic APIキー |

### 2. LLMプロバイダーの選択

GitHub Actionsの環境変数で使用するLLMプロバイダーを指定できます。以下のいずれかを設定してください

| 環境変数名 | 値 | 説明 |
|-------------|----|------|
| `LLM_PROVIDER` | `openai` / `anthropic` | 使用するLLMプロバイダーを指定 |

### 3. ワークフローでの使用例

```yaml
name: License Scan

on:
  push:
    branches: [main]
  pull_request:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Scan licenses
        uses: cmscom/osslens-actions@v0.1.0
        with:
          file: requirements.txt
          output: license-report.json
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          LLM_PROVIDER: openai
```

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

詳細は、 [ポリシーガイド](docs/policy-guide-ja.md) を参照してください。

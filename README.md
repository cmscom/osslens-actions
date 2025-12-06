# osslens-actions

GitHub Actions for scanning OSS licenses.

## Product status

- Version: v0.1 (initial release)
- Development status: Alpha
- Warranty: None (use at your own risk; feedback welcome)
- Pricing: Free (paid plans may arrive later)

## Usage

Since this action uses an LLM, make sure to configure your OpenAI or Anthropic API key in GitHub Secrets before use.

### Basic scan

```yaml
- name: Scan licenses
  uses: cmscom/osslens-actions@v0.1
  with:
    file: requirements.txt
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    LLM_PROVIDER: openai
```

### Scan with report outputs

```yaml
- name: Scan licenses with reports
  id: scan
  uses: cmscom/osslens-actions@v0.1
  with:
    file: requirements.txt
    output: license-report.json
    markdown: license-report.md
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    LLM_PROVIDER: openai

- name: Show results
  run: |
    echo "Packages: ${{ steps.scan.outputs.packages-count }}"
    echo "Violations: ${{ steps.scan.outputs.violations-count }}"
```

### Scan with policy enforcement

```yaml
- name: Scan with policy
  id: scan
  uses: cmscom/osslens-actions@v0.1
  with:
    file: requirements.txt
    policy: policy.json
    output: report.json
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    LLM_PROVIDER: openai

- name: Fail on violations
  if: steps.scan.outputs.violations-count != '0'
  run: exit 1
```

## Inputs

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `file` | Yes | - | Dependency file to scan |
| `output` | No | - | JSON output file path |
| `markdown` | No | - | Markdown report file path |
| `policy` | No | - | Policy definition file path |
| `format` | No | auto | File format (auto, requirements, pylock, etc.) |
| `verbose` | No | false | Enable verbose logging |
| `debug` | No | false | Debug mode |

## Outputs

| Parameter | Description |
|-----------|-------------|
| `result` | Scan result (success/failure) |
| `packages-count` | Number of scanned packages |
| `violations-count` | Number of policy violations |
| `report-path` | Path of the generated report |

## Viewing and downloading scan results

Assumes the scan steps above already generated `markdown` and `output`.

### Show in Job Summary

Use `$GITHUB_STEP_SUMMARY` to render the Markdown report on the workflow summary page so you can see results immediately in the Actions run UI.

```yaml
- name: Display results in Job Summary
  run: |
    echo "## License Scan Results" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "- **Packages scanned**: ${{ steps.scan.outputs.packages-count }}" >> $GITHUB_STEP_SUMMARY
    echo "- **Violations found**: ${{ steps.scan.outputs.violations-count }}" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    cat license-report.md >> $GITHUB_STEP_SUMMARY
```

**Where to view**: GitHub → Actions → Workflow run → Summary tab

### Download as artifacts

Use `actions/upload-artifact` to download the report files as a ZIP from the run page.

```yaml
- name: Upload reports as artifact
  uses: actions/upload-artifact@v4
  with:
    name: license-reports
    path: |
      license-report.json
      license-report.md
    retention-days: 30  # Retention period (defaults to repo settings if omitted)
```

**Where to download**: GitHub → Actions → Workflow run → Artifacts section

### Complete example combining both

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
        uses: cmscom/osslens-actions@v0.1
        with:
          file: requirements.txt
          policy: policy.json
          output: license-report.json
          markdown: license-report.md
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          LLM_PROVIDER: openai

      # Show results in Job Summary
      - name: Display results in Job Summary
        run: |
          echo "## License Scan Results" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Item | Value |" >> $GITHUB_STEP_SUMMARY
          echo "|------|-------|" >> $GITHUB_STEP_SUMMARY
          echo "| Packages | ${{ steps.scan.outputs.packages-count }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Violations | ${{ steps.scan.outputs.violations-count }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Result | ${{ steps.scan.outputs.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### Detailed Report" >> $GITHUB_STEP_SUMMARY
          cat license-report.md >> $GITHUB_STEP_SUMMARY

      # Upload as artifacts
      - name: Upload reports
        uses: actions/upload-artifact@v4
        with:
          name: license-reports
          path: |
            license-report.json
            license-report.md

      # Fail the job if violations exist
      - name: Check for violations
        if: steps.scan.outputs.violations-count != '0'
        run: |
          echo "::error::Found ${{ steps.scan.outputs.violations-count }} license violations"
          exit 1
```

## Supported file formats

- Python: `requirements.txt`, `pylock.toml`
- Node.js: `package-lock.json`
- Go: `go.sum`
- Ruby: `Gemfile.lock`
- Java: `pom.xml`

## Secrets

Pass secrets such as the OpenAI API key via GitHub Secrets.

### 1. Configure GitHub Secrets

In your repository, go to **Settings** → **Secrets and variables** → **Actions** and add:

| Secret name | Description |
|-------------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |

### 2. Choose an LLM provider

Select the LLM provider via environment variable:

| Env var | Value | Description |
|---------|-------|-------------|
| `LLM_PROVIDER` | `openai` / `anthropic` | Select the LLM provider |

### 3. Workflow example

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
        uses: cmscom/osslens-actions@v0.1
        with:
          file: requirements.txt
          output: license-report.json
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          LLM_PROVIDER: openai
```

## policy.json structure

### Basic structure

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

See the [Policy Guide](docs/policy-guide.md) for details.

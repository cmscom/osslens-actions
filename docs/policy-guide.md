# Policy Guide

> How to configure license policy checks and the structure of `policy.json`.
>
> **Note**: Policy checks work for all supported formats (Python/Node.js/Go/Ruby/Java, etc.).

## Table of Contents

- [Policy Check Overview](#policy-check-overview)
- [policy.json Structure](#policyjson-structure)
- [Rule Configuration](#rule-configuration)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Customization](#customization)

## Policy Check Overview

### What is a license policy?

A license policy defines which OSS licenses your organization allows or forbids.

### Why do you need it?

- **Legal risk management**: Prevent unintended copyleft inclusion.
- **Compliance**: Align with company policy.
- **Automation**: Enforce checks in CI/CD.

## policy.json Structure

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

### Field descriptions

- **version**: Policy schema version (currently only `1`).
- **default_status**: Behavior for licenses not covered by rules.
  - `allow`: Allowed to use.
  - `review`: Needs review.
  - `deny`: Prohibited.
- **rules**: Array of per-license rules.

## Rule Configuration

### Rule shape

```json
{
  "license": "MIT",
  "status": "allow",
  "reason": "Permissive license suitable for commercial use"
}
```

### Fields

- **license**: License name (SPDX identifier recommended).
  - Examples: `MIT`, `Apache-2.0`, `GPL-3.0-only`
- **status**:
  - `allow`: Allowed.
  - `review`: Needs review (warning).
  - `deny`: Forbidden (build fails).
- **reason**: Explanation (optional but recommended).

### SPDX identifiers

Refer to the [SPDX License List](https://spdx.org/licenses/) for exact names:

- ✅ Correct: `GPL-3.0-only`, `Apache-2.0`
- ❌ Incorrect: `GPL-3.0`, `Apache 2.0`

## Examples

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

### Classification notes

#### allow

- **MIT**: Very permissive; commercial use allowed.
- **Apache-2.0**: Includes patent grant; enterprise-friendly.
- **BSD-3-Clause**: Permissive BSD; commercial use allowed.
- **ISC**: MIT-like simple permissive license.

#### deny

- **GPL-3.0-only**: Strong copyleft; incompatible with proprietary software.
- **GPL-2.0-only**: Copyleft; distribution restrictions apply.
- **AGPL-3.0-only**: Network copyleft; watch for SaaS obligations.
- **Unknown**: Disallow until the license is identified.

#### review

- **LGPL-3.0-only**: Weak copyleft; linking considerations.
- **MPL-2.0**: File-level copyleft; review required.
- **Others (default_status)**: Anything not covered by rules requires review.

## Best Practices

### Policy samples by organization type

#### Startup (permissive)

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

#### Enterprise (strict)

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

### Choosing default_status

- **allow**: Internal tools, prototypes (higher risk).
- **review**: Startups/SMBs (recommended).
- **deny**: Enterprises, regulated industries (safest).

### Handling Unknown

Always set unknown licenses to `deny`:

```json
{
  "license": "Unknown",
  "status": "deny",
  "reason": "License must be explicitly identified before use"
}
```

## Customization

### Tuning for your project

1. **Copy examples/policy.json**

```bash
cp examples/policy.json my-policy.json
```

2. **Edit to match your org policy**

```json
{
  "version": 1,
  "default_status": "review",
  "rules": [
    // Add allowed licenses
    {"license": "MIT", "status": "allow", "reason": "Approved by org"},
    // Add prohibited licenses
    {"license": "AGPL-3.0-only", "status": "deny", "reason": "Not SaaS-compatible"}
  ]
}
```

3. **Apply the policy and scan**

```bash
# Python
oss-license-scan scan requirements.txt -p my-policy.json -o report.json

# Node.js
oss-license-scan scan package-lock.json -p my-policy.json -o report.json

# Others (Go, Ruby, Java) follow the same pattern
```

### License compatibility considerations

License compatibility matrix:

| Using license | MIT | Apache-2.0 | GPL-3.0 | AGPL-3.0 |
|---------------|-----|------------|---------|----------|
| MIT           | ✅  | ✅         | ⚠️      | ⚠️       |
| Apache-2.0    | ✅  | ✅         | ⚠️      | ⚠️       |
| GPL-3.0       | ✅  | ✅         | ✅      | ⚠️       |
| AGPL-3.0      | ✅  | ✅         | ✅      | ✅       |

- ✅: Compatible.
- ⚠️: Conditionally compatible (verify details).

### Phased rollout

Introducing to an existing project:

1. **Phase 1**: Scan without a policy to baseline current state.
2. **Phase 2**: Set only `review` rules; inspect warnings.
3. **Phase 3**: Add `deny` rules; integrate with CI/CD.

```bash
# Phase 1: Baseline (adjust target file to your project)
oss-license-scan scan requirements.txt -o baseline.json     # Python
oss-license-scan scan package-lock.json -o baseline.json    # Node.js
oss-license-scan scan go.sum -o baseline.json               # Go

# Phase 2: review warnings
oss-license-scan scan requirements.txt -p policy-review-only.json

# Phase 3: enforce deny
oss-license-scan scan requirements.txt -p policy-strict.json
```

## Related Docs

- [Reference Guide](./reference.md): Exit codes.
- [CI/CD Integration](./ci-cd-integration.md): Failing builds on policy violations.
- [SPDX License List](https://spdx.org/licenses/): Official license identifiers.

---

Last updated: 2025-11-27

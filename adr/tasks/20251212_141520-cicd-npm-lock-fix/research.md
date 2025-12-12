## 🔍 Feature Area: CI/CD npm package lock synchronization issue

## Summary

The CI/CD pipeline fails during `npm ci` in the frontend because `package.json` specifies newer versions of dependencies than what's locked in `package-lock.json`. The lockfile contains older versions (e.g., `openapi-typescript@7.9.1`, `stylelint@16.23.1`) while `package.json` requests newer versions (`^7.10.1`, `^16.26.1`). This indicates someone manually edited `package.json` without running `npm install` to regenerate the lockfile.

## Code Paths Found

| File                         | Lines   | Purpose                                       | Action    |
| ---------------------------- | ------- | --------------------------------------------- | --------- |
| `.github/workflows/lint.yml` | 70-72   | Frontend CI job runs `npm ci` to install deps | reference |
| `.github/workflows/lint.yml` | 105-107 | API types check job also runs `npm ci`        | reference |
| `frontend/package.json`      | 62      | Specifies `openapi-typescript: "^7.10.1"`     | reference |
| `frontend/package.json`      | 64      | Specifies `stylelint: "^16.26.1"`             | reference |
| `frontend/package-lock.json` | 10349   | Locked to `openapi-typescript@7.9.1`          | modify    |
| `frontend/package-lock.json` | 12006   | Locked to `stylelint@16.23.1`                 | modify    |

**Action legend**: `modify` (needs changes), `reference` (read only)

## Key Patterns

- **package.json version specs**: Caret ranges (`^`) allow minor/patch updates
- **npm ci behavior**: Requires exact match between `package.json` and lockfile
- **CI/CD workflow**: Uses Node.js 20 with npm caching on `package-lock.json`

## Root Cause

1. Someone edited `package.json` directly to bump `openapi-typescript` from `^7.4.0` → `^7.10.1`
2. Someone edited `package.json` directly to bump `stylelint` from `^16.0.0` → `^16.26.1`
3. The lockfile was never regenerated with `npm install`
4. Additional missing/outdated transitive dependencies:
   - `@csstools/css-syntax-patches-for-csstree@1.0.20`
   - `@dual-bundle/import-meta-resolve@4.2.1`
   - `debug@4.4.3`
   - `file-entry-cache@11.1.1`
   - `flat-cache@6.1.19`
   - `cacheable@2.3.0`
   - `hookified@1.14.0`
   - `@cacheable/memory@2.0.6`
   - `@cacheable/utils@2.3.2`
   - `keyv@5.5.5`
   - `@keyv/serialize@1.1.1`
   - And more...

## Integration Points

- CI workflow (.github/workflows/lint.yml:70-72) → npm ci → package-lock.json integrity check
- CI workflow (.github/workflows/lint.yml:105-107) → npm ci → package-lock.json integrity check

## Constraints Discovered

- **npm ci behavior**: Enforces strict version matching to ensure reproducible installs
- **Node version**: CI uses Node 20 (`.github/workflows/lint.yml:66`)
- **npm version**: Local environment has npm 10.9.3 and node v22.20.0
- **Cache strategy**: GitHub Actions caches npm deps based on lockfile hash (`.github/workflows/lint.yml:67-68`)

## Solution

Run `npm install` in the `frontend/` directory to:

1. Resolve all dependencies according to version ranges in `package.json`
2. Regenerate `package-lock.json` with exact resolved versions
3. Ensure all transitive dependencies are properly locked
4. Commit the updated `package-lock.json`

This will synchronize the lockfile with the current `package.json` specifications and allow CI to pass.

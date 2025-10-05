# Known Issues

This document tracks known limitations and issues in the finances package.

## Test Infrastructure

### E2E Test Subprocess Failures (RESOLVED)

**Issue**: Some E2E tests could fail with `FileNotFoundError: [Errno 2] No such file or directory: 'uv'`

**Cause**: Early E2E test implementations passed custom `env` dict to `subprocess.run()` without merging with `os.environ`, causing PATH and other critical environment variables to be lost.

**Fix Applied**: Commit b001e01 (2025-10-05) fixed environment merging in all E2E test helpers.
All subprocess calls now properly merge custom environment variables with `os.environ` to preserve PATH.

**Status**: ✅ **RESOLVED** as of 2025-10-05.

E2E tests should now run reliably in any environment where `uv` is installed and in PATH.

## CLI Commands

### Incomplete Error Handling

Several CLI commands have minimal error handling for edge cases:

1. **Missing YNAB Data**: Some commands don't gracefully handle missing YNAB cache files
2. **Invalid Date Formats**: Date parsing could be more robust
3. **Missing Configuration**: Some commands assume config values exist

**Status**: Low priority - most users won't encounter these scenarios.

### Parameter Validation

Some CLI commands accept invalid parameter combinations without warning:

1. `finances flow go --nodes nonexistent` - doesn't validate node names
2. Date range filters may not validate that start < end

**Status**: Low priority - documented behavior.

## Flow System

### Change Detection Limitations

Current change detection is file-existence based and may not detect:
- Content changes in cached files without timestamp updates
- Semantic changes that don't affect file modification times

**Status**: Acceptable for current use case.

## Data Processing

### Currency Precision

All currency calculations use integer arithmetic (cents or milliunits).
This ensures precision but means:
- Division operations must use integer division
- Rounding happens at integer level
- Display formatting must use modulo operations

**Status**: By design - not an issue.

### Multi-Account Amazon Support

Amazon transaction matching requires manual account name detection from directory structure.
Format: `YYYY-MM-DD_accountname_amazon_data/`

**Status**: By design - works as intended.

## Security & Privacy

### Test Data

All test data MUST be synthetic. Never commit:
- Real account balances or IDs
- Real transaction details
- Personal information (emails, phone numbers)
- Real financial account numbers

**Status**: Enforced by code review.

### YNAB API Access

The YNAB sync functionality requires API tokens stored in `.env`.
Ensure `.env` is never committed.

**Status**: Protected by `.gitignore`.

---

**Last Updated**: 2025-10-05
**Maintained By**: Project maintainers

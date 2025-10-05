# Development T-Dos

## Minor Items

- [X] Add additional Markdown formatting rules to @CONTRIBUTING.md and @CLAUDE.md,
        then apply them to all existing Markdown files:
    - [X] Every sentence, list item, or other full sentence-like line should end with a period.
    - [X] Trailing whitespace should be removed from lines,
            except when required by Markdown's formatting rules,
            such as for code blocks inside a list.
    - [X] Files should end with a line break, per POSIX.
- [X] Rename the YNAB "mutations" to "edits".
- [X] JSON file outputs should be pretty-printed, for readability and searchability.

## Major Items

- [ ] Figure out what version of Python we want to target,
        and remove any unnecessary compatibility comprises.
- [ ] Remove the error ignores in pyproject.toml and resolve any resulting issues.
- [X] Implement @dev/specs/2025-09-21-code-quality.md, to add lints and CI and such.
    - [X] Pre-commit hooks configured (Black, Ruff, file hygiene).
    - [X] GitHub Actions CI/CD workflow with all quality checks.
    - [X] Tool configurations (Black, Ruff, Mypy strict mode).
    - [X] Zero mypy errors achieved.
    - [X] IDE integration (.vscode/ settings, extensions, debugging).
    - [X] Renovate bot configuration for automated dependency updates.
    - [X] Status badges in README.md.
    - [X] Documentation updated with setup instructions.
    - [ ] Fix 2 failing tests in retirement service.
    - [ ] Increase test coverage from 56% to 60% threshold.
- [ ] Ensure there's one canonical end-to-end test that covers all major functionality.
      As the human overseer of a project mostly written by Claude Code,
        I'll keep an eye on this test case to ensure things haven't gone off the rails.

## Incomplete CLI Implementations

These CLI commands have placeholder implementations that need to be completed:

### Amazon CLI
- [ ] `finances amazon match` - Integrate with existing batch matching logic
      (placeholder at src/finances/cli/amazon.py:79).
- [ ] `finances amazon match-single` - Integrate with existing single transaction matching logic
      (placeholder at src/finances/cli/amazon.py:167).

### Apple CLI
- [ ] `finances apple match` - Integrate with existing batch matching logic
      (placeholder at src/finances/cli/apple.py:69).
- [ ] `finances apple match-single` - Integrate with existing single transaction matching logic
      (placeholder at src/finances/cli/apple.py:156).

### YNAB CLI
- [ ] `finances ynab apply-edits` - Implement YNAB API integration for applying transaction edits
      (placeholder at src/finances/cli/ynab.py:224).
- [ ] `finances ynab sync-cache` - Implement YNAB API integration for syncing cache data
      (placeholder at src/finances/cli/ynab.py:269).

### CashFlow CLI
- [ ] `finances cashflow report` - Migrate existing analysis logic for structured reporting
      (placeholder at src/finances/cli/cashflow.py:188).
- [ ] `finances cashflow forecast` - Migrate existing analysis logic for forecasting
      (placeholder at src/finances/cli/cashflow.py:238).

### Retirement CLI
- [ ] `finances retirement update --non-interactive` - Implement file-based input for balance updates
      (placeholder at src/finances/cli/retirement.py:178).

## Architecture and Testing Refactoring

These items require refactoring to enable proper unit testing:

- [ ] Extract flow graph JSON serialization into testable function
      (currently tightly coupled to CLI at src/finances/cli/flow.py).
- [ ] Make flow node registry inspectable and resettable for testing
      (currently uses module-level state that's difficult to test).
- [ ] Remove placeholder in CLICommandNode.execute()
      (src/finances/core/flow.py:303 - needs actual CLI command invocation).

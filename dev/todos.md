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
- [ ] Fix potential data loss risk in retirement CLI non-interactive mode
      (src/finances/cli/retirement.py:177-203).
      Currently --output-file serves dual purpose as both input and output file,
      which could lead to accidental overwrites.
      Recommendation: Add separate --input-file option for non-interactive mode.
      Context: PR #8 code review feedback - deferred for future enhancement.
- [ ] Make cash flow analysis more lenient for test environments.
      Currently requires 6+ months of historical data, which causes E2E tests to exclude it.
      Recommendation: Detect test environment or allow configurable minimum data requirements
      so that cash_flow_analysis node can be included in comprehensive flow E2E tests.
      Context: PR #9 - excluded from test_flow_go_interactive_mode due to data requirements.

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
    - [X] Fix 2 failing tests in retirement service.
    - [X] Increase test coverage from 56% to 60% threshold (currently at 74%).
- [ ] Ensure there's one canonical end-to-end test that covers all major functionality.
      As the human overseer of a project mostly written by Claude Code,
        I'll keep an eye on this test case to ensure things haven't gone off the rails.

## Incomplete CLI Implementations

These CLI commands have placeholder implementations that need to be completed:

### Amazon CLI
- [X] `finances amazon match` - Integrate with existing batch matching logic.
      Completed with full data loading and matching pipeline.
- [X] `finances amazon match-single` - Integrate with existing single transaction matching logic.
      Completed with interactive result display.

### Apple CLI
- [X] `finances apple match` - Integrate with existing batch matching logic.
      Completed using existing batch_match_transactions function.
- [X] `finances apple match-single` - Integrate with existing single transaction matching logic.
      Completed with proper dataclass serialization.

### YNAB CLI
- [X] `finances ynab apply-edits` - Implement YNAB API integration for applying transaction edits.
      Completed with manual workflow instructions (YNAB doesn't support programmatic splits).
- [X] `finances ynab sync-cache` - Implement YNAB API integration for syncing cache data.
      Completed with delegation to existing `ynab` CLI tool via subprocess.

### CashFlow CLI
- [X] `finances cashflow report` - Migrate existing analysis logic for structured reporting.
      Completed with JSON/CSV export formats.
- [X] `finances cashflow forecast` - Migrate existing analysis logic for forecasting.
      Completed with 30/60/90-day projections and risk assessment.

### Retirement CLI
- [X] `finances retirement update --non-interactive` - Implement file-based input for balance updates.
      Completed with JSON/YAML input file support.

## Architecture and Testing Refactoring

These items require refactoring to enable proper unit testing:

- [ ] Extract flow graph JSON serialization into testable function
      (currently tightly coupled to CLI at src/finances/cli/flow.py).
- [ ] Make flow node registry inspectable and resettable for testing
      (currently uses module-level state that's difficult to test).
- [X] Remove placeholder in CLICommandNode.execute()
      (CLICommandNode class no longer exists - refactored to use create_cli_executor pattern).

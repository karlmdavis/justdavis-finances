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
- [ ] Improve flow_test_env synthetic test data to create realistic transaction matches.
      Currently YNAB transactions, Amazon orders, and Apple receipts are generated independently,
      so matchers likely find no actual matches in E2E flow tests.
      Recommendation: Generate coordinated test data where some YNAB transactions have
      corresponding Amazon orders or Apple receipts with matching amounts and dates.
      This would provide more realistic E2E testing of the matching algorithms through the flow system.
      Context: flow_test_env fixture creates ZIP files and parsed data but matchers find no matches.

## Major Items

- [ ] Get more serious about data flow schemas.
    - [ ] Apple receipt parsing and Amazon order parsing should each produce result objects modeled
            by a class and JSON schema that most naturally represent the actual data.
    - [ ] The Apple and Amazon matchers should use those parsed object classes to load parse results.
          They should then apply any transformations needed to each record via a view transform class,
            e.g., AppleReceipt --> AppleReceiptForMatching.
          That view class should be the only format used for that "side" of the data in matching logic.
    - [ ] The split edit generator input should be modeled by a YnabTransactionExternalDetails class,
            or something like it, which represents the receipt/order matches that were found,
            associating a YNAB transaction ID with a potential match's line items.
          The Apple and Amazon matchers should produce their output in this exact format/class.
    - [ ] Every step after receipt/order parsing should use standard primitive types
            for currency and dates.
- [ ] Figure out what version of Python we want to target,
        and remove any unnecessary compatibility comprises.
- [ ] Make `--nodes-excluded` not transitive, as this breaks its usefulness in a test scenario.
      Either that or add a non-transitive `--nodes-skipped`.
- [X] Remove the error ignores in pyproject.toml and resolve any resulting issues.
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
- [X] Ensure there's one canonical end-to-end test that covers all major functionality.
      As the human overseer of a project mostly written by Claude Code,
        I'll keep an eye on this test case to ensure things haven't gone off the rails.
      Completed: tests/e2e/test_flow_system.py::test_flow_interactive_execution_with_matching
      implements comprehensive flow testing with imperative approach, test-mode markers,
      coordinated test data, and full output logging for debugging.

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
- [ ] **Decentralize Flow Node Registration (Post-Phase 1)**
      - **Problem**: Current flow system has centralized architecture that's hard to maintain:
        - Giant `setup_flow_nodes()` function in `src/finances/cli/flow.py`.
        - Separate `create_data_summary_functions()` returning dict of functions.
        - All node registration logic coupled in one place.
        - Far from the actual domain code each node operates on.
      - **Proposed Solution**: Distribute flow node definitions to their respective domain modules
        using a class-based approach.
        Each domain module would have a `flow.py` file with `FlowNode` subclasses:
        - `src/finances/ynab/flow.py` → `YnabSyncFlowNode` class.
        - `src/finances/amazon/flow.py` → `AmazonUnzipFlowNode`, `AmazonMatchingFlowNode` classes.
        - `src/finances/apple/flow.py` → `AppleEmailFetchFlowNode`, etc.
      - **Benefits**:
        - Each domain owns its flow integration logic.
        - Changes to a domain's flow behavior stay localized.
        - Easier to understand and maintain.
        - Better encapsulation (no giant function dict).
        - More testable (can test node classes in isolation).
      - **When to Address**: After Phase 1 is complete and stable.
        This is a refactoring that doesn't change functionality, but improves maintainability.
- [ ] **Consider Extracting HTML Parsing from email_fetcher.py (Post-Phase 1)**
      - **Current State**: `apple/email_fetcher.py` does IMAP fetch + HTML/text extraction + file saving (4 files per email).
      - **Concern**: HTML extraction logic mixed with IMAP operations makes extraction untestable without credentials.
      - **Proposed Refactor**: Move HTML/text extraction to `apple/parser.py` or new `apple/html_extractor.py`.
        - `email_fetcher.py`: IMAP fetch only → saves `.eml` files
        - New extraction layer: reads `.eml` → extracts/saves `.html`, `.txt`, `.json` metadata
        - `parser.py`: reads `.html` → parses receipt data
      - **Benefits**:
        - HTML extraction becomes testable without IMAP credentials
        - Cleaner separation of concerns (IMAP vs parsing)
        - Could add new FlowNode: `apple_html_extract` between `apple_email_fetch` and `apple_receipt_parsing`
      - **Trade-offs**:
        - Breaking change to file layout workflow
        - Current 4-file approach works fine in production
        - Adds complexity with extra node
      - **When to Address**: Low priority - only if testing or maintenance pain becomes significant.
        Current approach is functional, this is purely architectural improvement.

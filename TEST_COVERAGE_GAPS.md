# Test Coverage Gaps: E2E to Integration/Unit Migration

This document tracks functionality that was previously covered by E2E tests but should instead be
covered by integration or unit tests.
These items were removed during the E2E test quality overhaul (2025-10-05).

## Purpose

E2E tests should validate **complete user workflows** via subprocess execution.
They should NOT test individual flags, parameters, or output formats.
Those concerns are better suited for integration or unit tests.

## Removed E2E Tests and Recommended Coverage

### Flow System (14 tests removed)

#### CLI Parameter Testing (Should be Integration Tests)

**Removed Tests**:
1. `test_flow_validate_verbose` - Verified --verbose flag shows execution levels
2. `test_flow_go_verbose_output` - Verified --verbose shows detailed execution info
3. `test_flow_go_non_interactive` - Verified --non-interactive doesn't prompt
4. `test_flow_go_skip_archive` - Verified --skip-archive prevents archive creation
5. `test_flow_go_force_mode` - Verified --force executes all nodes
6. `test_flow_go_with_node_filtering` - Verified --nodes filters specific nodes
7. `test_flow_go_multiple_nodes_filtering` - Verified multiple --nodes flags
8. `test_flow_go_date_range_filtering` - Verified --start and --end parameters
9. `test_flow_go_confidence_threshold` - Verified --confidence-threshold parameter
10. `test_flow_go_perf_tracking` - Verified --perf flag

**Recommended Coverage**:
- **Integration tests** in `tests/integration/test_flow_integration.py`:
  - Test parameter binding between Click and flow engine
  - Test that flags modify FlowContext correctly
  - Use CliRunner, not subprocess

**Example**:
```python
def test_flow_verbose_flag_sets_context():
    runner = CliRunner()
    result = runner.invoke(flow, ['go', '--verbose', '--dry-run'])
    # Verify verbose output appears in result.output
```

#### Output Format Testing (Should be Unit Tests)

**Removed Tests**:
11. `test_flow_graph_json_format` - Verified JSON output structure

**Recommended Coverage**:
- **Unit tests** in `tests/unit/test_flow/test_flow_engine.py`:
  - Test graph serialization to JSON
  - Test JSON structure matches expected schema
  - No CLI execution needed

#### Implementation Verification (Should be Integration/Unit Tests)

**Removed Tests**:
12. `test_flow_graph_shows_all_standard_nodes` - Verified node registration
13. `test_flow_integration_validate_then_graph` - Artificial sequential execution
14. `test_flow_validate_catches_invalid_nodes` - Didn't actually test errors!

**Recommended Coverage**:
- **Unit tests**: Test node registration in FlowNodeRegistry
- **Integration tests**: Test that CLI commands invoke flow engine correctly
- Fix test #14 or delete (it expected success, not errors!)

---

### Amazon CLI (5 tests removed)

#### Parameter Testing (Should be Integration Tests)

**Removed Tests**:
1. `test_amazon_match_with_date_range` - Verified --start/--end date filtering
2. `test_amazon_match_output_directory` - Verified --output-dir parameter
3. `test_amazon_match_with_verbose_output` - Verified --verbose flag
4. `test_amazon_match_with_split_disabled` - Verified --disable-split flag
5. `test_amazon_unzip_with_account_filter` - Verified --accounts parameter

**Recommended Coverage**:
- **Integration tests** in `tests/integration/test_amazon_integration.py`:
  - Test date filtering logic (not just that parameter is accepted)
  - Test output directory creation with custom paths
  - Test verbose logging behavior
  - Test split payment matching can be disabled
  - Test account filtering logic

**Example**:
```python
def test_match_filters_by_date_range():
    # Setup: Transactions spanning 90 days
    # Test: Match with 30-day window
    # Verify: Only transactions in range are processed
```

---

### Apple CLI (5 tests removed)

#### Output Format Validation (Should be Unit Tests)

**Removed Tests**:
1. `test_apple_parse_receipts_output_format` - Verified JSON structure

**Recommended Coverage**:
- **Unit tests** for receipt parser output schema validation
- Test JSON serialization logic directly, not via CLI

#### Parameter Testing (Should be Integration Tests)

**Removed Tests**:
2. `test_apple_parse_verbose_output` - Verified --verbose flag
3. `test_apple_match_with_apple_id_filter` - Verified --apple-ids parameter
4. `test_apple_match_verbose_output` - Verified --verbose flag

**Recommended Coverage**:
- **Integration tests** in `tests/integration/test_apple_integration.py`:
  - Test verbose logging behavior
  - Test Apple ID filtering logic (not just parameter acceptance)

#### Incomplete Tests (Should be Fixed or Deleted)

**Removed Tests**:
5. `test_apple_match_invalid_date_format` - Ran command but didn't verify error!

**Recommended Coverage**:
- **Integration test**: Test date parsing with invalid formats, verify ValueError raised
- Or **delete**: If Click already validates date format, no need to test

---

### YNAB CLI (3 tests removed)

#### Placeholder Implementation Tests (Should NOT Exist)

**Removed Tests**:
1. `test_ynab_sync_cache_dry_run` - Tested placeholder that prints "TODO"
2. `test_ynab_apply_edits_dry_run` - Tested placeholder implementation

**Recommended Coverage**:
- **None until implemented**: Don't test placeholders
- When implemented: Add integration tests with mocked YNAB API

**Example (future)**:
```python
@patch('ynab.api.update_transaction')
def test_apply_edits_calls_ynab_api(mock_api):
    # Test that edits are sent to YNAB API correctly
```

#### Parameter Testing (Should be Integration Tests)

**Removed Tests**:
3. `test_ynab_generate_splits_with_dry_run` - Verified --dry-run creates different filename

**Recommended Coverage**:
- **Integration test**: Verify dry-run flag prevents file writes or modifies behavior
- Test the business logic, not just filename differences

---

### Analysis CLI (7 tests removed)

#### Output Format Testing (Should be Integration Tests)

**Removed Tests**:
1. `test_cashflow_analyze_output_formats` - Verified PNG vs SVG output

**Recommended Coverage**:
- **Integration test**: Test chart rendering with different formats
- Use matplotlib directly, not via CLI subprocess

#### Parameter Testing (Should be Integration Tests)

**Removed Tests**:
2. `test_cashflow_analyze_date_range` - Verified --start/--end parameters
3. `test_cashflow_analyze_account_filter` - Verified --accounts parameter
4. `test_cashflow_analyze_verbose_mode` - Verified --verbose flag
5. `test_retirement_update_with_date` - Verified --date parameter
6. `test_retirement_update_output_file` - Verified --output-file parameter
7. `test_retirement_update_dry_run` - Tested doing nothing (no updates)

**Recommended Coverage**:
- **Integration tests** in `tests/integration/test_analysis_integration.py`:
  - Test date range filtering logic
  - Test account filtering logic
  - Test custom output paths
  - Test verbose logging
- **Not needed**: test_retirement_update_dry_run (no value)

---

## General Principles

### What Should Be E2E Tests?

✅ **Complete user workflows**:
- User downloads Amazon data → unzips → matches → generates splits
- User parses Apple receipts → matches transactions → generates splits
- User runs `flow go` → system orchestrates all steps → produces correct output

✅ **Critical error scenarios**:
- Missing required data files
- Corrupted input files
- No matches found (legitimate scenario)

✅ **User-facing behavior**:
- Command succeeds/fails with expected messages
- Output files are created in expected locations
- Help text is displayed

### What Should Be Integration Tests?

✅ **CLI parameter behavior**:
- Flags modify execution correctly (--verbose, --dry-run, --force)
- Filters work correctly (--start, --end, --accounts)
- Output paths can be customized

✅ **Component integration**:
- CLI invokes business logic correctly
- Click commands bind to Python functions properly
- Configuration is loaded and applied

✅ **Data flow**:
- Input files are read correctly
- Output files are written to correct locations
- Data transformations happen correctly

### What Should Be Unit Tests?

✅ **Business logic**:
- Matching algorithms (Amazon, Apple)
- Split calculations
- Confidence scoring

✅ **Data structures**:
- JSON serialization/deserialization
- Schema validation
- Data model correctness

✅ **Utilities**:
- Date parsing
- Currency conversion
- String formatting

---

## Action Items

### High Priority

1. **Create integration test suite for CLI parameters**:
   - `tests/integration/test_cli_parameters.py`
   - Test flag behavior for all commands
   - Use CliRunner instead of subprocess

2. **Move output format tests to unit tests**:
   - Test JSON schema validation directly
   - Test chart rendering with matplotlib mocks

3. **Delete or fix placeholder tests**:
   - Remove tests for unimplemented features
   - Add proper tests when features are implemented

### Medium Priority

4. **Document parameter testing strategy**:
   - Update `tests/README.md` with guidance
   - E2E tests should NOT test individual parameters
   - Use integration tests for parameter validation

5. **Create integration test templates**:
   - Provide examples of good integration tests
   - Show how to test CLI without subprocess

### Low Priority

6. **Audit remaining E2E tests**:
   - Ensure they test complete workflows
   - Ensure they provide user value
   - Consolidate similar tests

---

## Metrics

**E2E Tests Removed**: 34 tests
**Recommended Integration Tests to Add**: ~20 tests
**Recommended Unit Tests to Add**: ~5 tests

**Net Change**: Fewer total tests, better coverage of the right things

---

**Last Updated**: 2025-10-05
**Related PR**: Test Coverage Overhaul #6

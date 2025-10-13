# Phase 5: Test Suite Overhaul

## Goal

Refactor test suite to follow inverted pyramid: E2E > Integration > Unit.
Remove low-value tests, focus on tests that catch real bugs.

## Problem Statement

Current state:
- 295+ tests, many testing implementation details
- Excessive mocking in integration tests
- Low-value unit tests for trivial code
- Tests didn't catch bugs in PR #8, #9, #6

Target state:
- ~150-200 high-value tests
- E2E tests for complete user workflows
- Integration tests for domain operations
- Unit tests only for complex business logic
- Tests catch real bugs before they reach production

## Key Changes

### 1. E2E Test Focus

**Primary test:** Complete `finances flow` execution

```python
def test_complete_financial_flow():
    """
    Test complete flow from start to finish.

    This is THE test that matters - if this passes, the system works.
    """
    # Setup test data
    # Run: finances flow --non-interactive
    # Verify:
    #   - YNAB synced
    #   - Amazon matched
    #   - Apple matched
    #   - Splits generated
    #   - YNAB updated
    #   - Cash flow analyzed
    #   - All outputs correct
```

**Secondary E2E tests:**
- Interactive mode (with pexpect)
- Error handling (missing data, API failures)
- Archive creation and restoration

### 2. Integration Test Patterns

Focus on real component interaction:

```python
def test_amazon_matching_integration():
    """Test Amazon CSV → Matcher → JSON output."""
    # Real CSV file
    # Real YNAB data
    # Real matcher
    # Minimal mocking (only YNAB API)
    # Verify match accuracy
```

### 3. Unit Test Candidates

Keep only for:
- Money operations (addition, conversion, formatting)
- FinancialDate operations (parsing, age calculation)
- Matching algorithms (confidence scoring, fuzzy matching)
- Transformers (Amazon → Normalized, Apple → Normalized)
- Complex business logic (split calculation)

### 4. Tests to Remove

Delete:
- Tests of private methods
- Tests of trivial getters/setters
- Tests of implementation details (graph algorithms, sorting)
- Tests requiring extensive mocking (5+ mocks)
- Tests of framework behavior (Click, pandas)
- Placeholder tests (testing unimplemented features)

## Testing Matrix

| Component | E2E | Integration | Unit |
|-----------|-----|-------------|------|
| finances flow | ✅ Primary | ❌ | ❌ |
| Node execution | ✅ Via flow | ✅ Individual nodes | ❌ |
| Data loading | ❌ | ✅ Real files | ❌ |
| Matching | ❌ | ✅ Real data | ✅ Algorithms |
| Transformers | ❌ | ✅ Input→Output | ✅ Edge cases |
| Money/Dates | ❌ | ❌ | ✅ Full coverage |
| DataStores | ❌ | ✅ Real I/O | ✅ Validation |

## Migration Strategy

### Step 1: Identify Test Value
- Review each existing test
- Classify as High/Medium/Low value
- Mark low-value tests for deletion

### Step 2: Write Missing E2E Tests
- Complete flow test
- Interactive flow test
- Error scenarios

### Step 3: Refactor Integration Tests
- Remove excessive mocking
- Use real files and data
- Keep only valuable assertions

### Step 4: Prune Unit Tests
- Delete implementation detail tests
- Delete trivial tests
- Keep complex logic tests

### Step 5: Update Documentation
- Document testing philosophy
- Provide examples of good/bad tests
- Update CONTRIBUTING.md

## Test Quality Metrics

Instead of coverage percentage, focus on:
- **Bug Detection Rate**: Do tests catch real bugs?
- **False Positive Rate**: Do tests break when they shouldn't?
- **Maintenance Cost**: How often do tests need updating?
- **Execution Time**: Can full suite run in <5 minutes?

Target metrics:
- 100% of E2E user workflows covered
- <2 minutes for unit + integration tests
- <30 seconds for unit tests alone
- Zero false positives in CI

## Definition of Done

- [ ] E2E test for complete flow
- [ ] All low-value tests removed
- [ ] Integration tests use real components
- [ ] Unit tests cover only complex logic
- [ ] Test suite runs in <5 minutes
- [ ] Documentation updated
- [ ] Tests catch bugs from PR #8, #9, #6

## Estimated Effort

- **Test Audit**: 4-6 hours
- **E2E Test Writing**: 6-8 hours
- **Integration Refactoring**: 8-10 hours
- **Unit Test Pruning**: 4-6 hours
- **Documentation**: 2-3 hours
- **Total**: 24-33 hours (4-5 work days)

## Can Parallelize With

Phase 4 (Domain Models) - test refactoring can happen while models are being updated.

## Dependencies

- Phase 1 complete (E2E tests target new CLI)
- Phase 2 complete (tests use Money/FinancialDate)
- Phase 3 helpful (DataStore makes integration tests easier)
- Phase 4 helpful (clean models make tests clearer)

Can start early, update tests as earlier phases complete.

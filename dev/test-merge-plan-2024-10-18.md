# Test Merge Plan - 2024-10-18

## Overview

After removing 67 low-value tests, a second analysis revealed 26 additional tests that are duplicative and can be merged through parameterization. This will reduce the test count from 385 to 359 (-6.8%) while maintaining 100% coverage.

## Identified Duplicate Groups (10 Total)

### Priority 1: High-Impact Merges (21 tests → 8 tests, saves 13)

#### Group 1: DataStore FileNotFound Tests
**Impact**: 10 tests → 1 test (saves 9 tests)

**Tests to merge**:
1. test_amazon/test_datastore.py::TestAmazonRawDataStore::test_load_raises_when_no_files
2. test_amazon/test_datastore.py::TestAmazonMatchResultsStore::test_load_raises_when_no_files
3. test_apple/test_datastore.py::TestAppleEmailStore::test_load_raises_when_no_directory
4. test_apple/test_datastore.py::TestAppleEmailStore::test_load_raises_when_no_files
5. test_apple/test_datastore.py::TestAppleReceiptStore::test_load_raises_when_no_files
6. test_apple/test_datastore.py::TestAppleMatchResultsStore::test_load_raises_when_no_files
7. test_ynab/test_datastore.py::TestYnabCacheStore::test_load_raises_when_no_transactions_file
8. test_ynab/test_datastore.py::TestYnabEditsStore::test_load_raises_when_no_files
9. test_analysis/test_datastore.py::TestCashFlowResultsStore::test_load_raises_when_no_directory
10. test_analysis/test_datastore.py::TestCashFlowResultsStore::test_load_raises_when_no_files

**Rationale**: All test the same DataStore interface contract - calling load() on empty store raises FileNotFoundError.

**Implementation**: Create single parameterized test in new file `tests/unit/test_core/test_datastore_interface.py`

#### Group 2: DataStore MatchResults Tests
**Impact**: 10 tests → 5 tests (saves 5 tests)

**Tests to merge** (amazon + apple have identical patterns):
- Amazon: test_load_returns_most_recent_match_results, test_load_raises_when_no_files, test_save_creates_timestamped_file, test_item_count_returns_match_count, test_item_count_returns_none_for_invalid_structure
- Apple: Same 5 tests with identical logic

**Rationale**: Exact same pattern for testing match results stores, only difference is domain.

**Implementation**: Parameterize on store class and domain

### Priority 2: Core Type Consolidation (10 tests → 4 tests, saves 6)

#### Group 3: FinancialDate Construction Tests
**Impact**: 5 tests → 2 tests (saves 3 tests)

**Tests to merge**:
1. test_dates.py::TestFinancialDateConstruction::test_from_date
2. test_dates.py::TestFinancialDateConstruction::test_from_string
3. test_dates.py::TestFinancialDateConstruction::test_from_string_custom_format
4. test_dates.py::TestFinancialDateConstruction::test_from_timestamp
5. test_dates.py::TestFinancialDateConstruction::test_today (keep separate due to dynamic value)

**Rationale**: All verify different construction methods produce correct FinancialDate.

**Implementation**: Parameterize on constructor method (4 tests), keep test_today separate

#### Group 4: Money Negative Construction Tests
**Impact**: 3 tests → 1 test (saves 2 tests)

**Tests to merge**:
1. test_money.py::TestMoneyNegativeAmounts::test_negative_from_cents
2. test_money.py::TestMoneyNegativeAmounts::test_negative_from_milliunits
3. test_money.py::TestMoneyNegativeAmounts::test_negative_from_dollars_string

**Rationale**: Same logic - verify negative amounts created correctly, only difference is constructor.

**Implementation**: Parameterize on constructor method

#### Group 5: Money Edge Cases
**Impact**: 2 tests → 1 test (saves 1 test)

**Tests to merge**:
1. test_money.py::TestMoneyEdgeCases::test_zero_amount
2. test_money.py::TestMoneyEdgeCases::test_large_amounts

**Rationale**: Both test boundary conditions for Money values.

**Implementation**: Parameterize on amount scenarios (zero, one million, ten million)

### Priority 3: Integration Test Consolidation (10 tests → 3 tests, saves 7)

#### Group 6: Archive Sequence Numbering
**Impact**: 3 tests → 1 test (saves 2 tests)

**Tests to merge**:
1. test_archive_management.py::TestDomainArchiver::test_get_next_sequence_number_no_existing_archives
2. test_archive_management.py::TestDomainArchiver::test_get_next_sequence_number_with_existing_archives
3. test_archive_management.py::TestDomainArchiver::test_get_next_sequence_number_ignores_malformed_names

**Rationale**: All test sequence number generation with different scenarios.

**Implementation**: Parameterize on existing archive scenarios

#### Group 7: Archive Cleanup
**Impact**: 2 tests → 1 test (saves 1 test)

**Tests to merge**:
1. test_archive_management.py::TestArchiveManager::test_cleanup_old_archives_keeps_recent
2. test_archive_management.py::TestArchiveManager::test_cleanup_old_archives_deletes_manifests_too

**Rationale**: Second test just adds manifest deletion verification - should be part of single comprehensive test.

**Implementation**: Combine into single test verifying both behaviors

#### Group 8: Change Detection - Server Knowledge
**Impact**: 2 tests → 1 test (saves 1 test)

**Tests to merge**:
1. test_change_detection.py::TestYnabSyncChangeDetector::test_detects_server_knowledge_change_accounts
2. test_change_detection.py::TestYnabSyncChangeDetector::test_detects_server_knowledge_change_categories

**Rationale**: Identical logic, different file type.

**Implementation**: Parameterize on file type (accounts vs categories)

#### Group 9: Change Detection - YNAB Transactions
**Impact**: 2 tests → 1 test (saves 1 test)

**Tests to merge**:
1. test_change_detection.py::TestAmazonMatchingChangeDetector::test_detects_ynab_transactions_update
2. test_change_detection.py::TestAppleMatchingChangeDetector::test_detects_ynab_transactions_update

**Rationale**: Character-for-character identical except detector class.

**Implementation**: Parameterize on detector class

#### Group 10: Change Detection - New Directories
**Impact**: 2 tests → 1 test (saves 1 test)

**Tests to merge**:
1. test_change_detection.py::TestAmazonMatchingChangeDetector::test_detects_new_amazon_directory
2. test_change_detection.py::TestAppleMatchingChangeDetector::test_detects_new_apple_export_directory

**Rationale**: Same pattern with different directory structures.

**Implementation**: Parameterize on detector and directory structure

## Implementation Summary

| Priority | Groups | Tests Before | Tests After | Tests Saved |
|----------|--------|--------------|-------------|-------------|
| Priority 1 | 2 | 20 | 6 | 14 |
| Priority 2 | 3 | 10 | 4 | 6 |
| Priority 3 | 5 | 11 | 5 | 6 |
| **TOTAL** | **10** | **41** | **15** | **26** |

**Final Test Count**: 385 → 359 (-6.8%, -26 tests)

## Benefits

1. **Reduced maintenance burden** - 26 fewer tests to update during refactoring
2. **Improved clarity** - Parameterized tests show test scenarios explicitly
3. **Easier to extend** - Add new test cases by adding parameters
4. **100% coverage maintained** - All scenarios still tested
5. **Better organization** - Related tests grouped logically

## Implementation Plan

### Phase 1: High-Impact Merges (Priority 1)
1. Create `tests/unit/test_core/test_datastore_interface.py` for DataStore contract tests
2. Merge 10 FileNotFound tests → 1 parameterized test
3. Merge 10 MatchResults tests → 5 parameterized tests
4. Delete original tests
5. Run test suite to verify (saves 14 tests)

### Phase 2: Core Type Consolidation (Priority 2)
1. Merge FinancialDate construction tests (saves 3)
2. Merge Money negative construction tests (saves 2)
3. Merge Money edge case tests (saves 1)
4. Run test suite to verify (saves 6 tests)

### Phase 3: Integration Test Consolidation (Priority 3)
1. Merge Archive sequence numbering (saves 2)
2. Merge Archive cleanup (saves 1)
3. Merge Change Detection tests (saves 3)
4. Run test suite to verify (saves 6 tests)

## Tests NOT Recommended for Merging

The following were intentionally NOT flagged as duplicates:

1. **Matcher confidence tests** - Domain-specific logic with different business rules
2. **Split calculator tests** - Different domain models and tax allocation logic
3. **FlowNode interface tests** - Already well-parameterized
4. **Archive archivable files tests** - Each tests distinct filtering behavior

## Success Criteria

- [ ] All 26 duplicate tests merged successfully
- [ ] Final test count: 359 tests
- [ ] All tests pass (100% pass rate)
- [ ] No loss of coverage or test scenarios
- [ ] Improved test organization and maintainability
- [ ] Documentation updated with merge results

## Risk Assessment

**Low Risk**: All merges are straightforward parameterization of identical test logic. No functional changes to production code.

**Mitigation**: Run full test suite after each phase to verify no regressions.

# TODO Audit Report

**Date**: 2025-10-18
**Phase**: Phase 6 - Documentation & Code Cleanup
**Task**: Task 1 - TODO Audit and Catalog

## Executive Summary

Comprehensive audit of all TODO/FIXME/XXX/HACK comments, TODO tracking files, and existing GitHub
  issues in the codebase.

**Findings**:
- **Source code TODOs**: 2 items (both in `src/finances/amazon/grouper.py`)
- **Test code TODOs**: 0 items (1 false positive - "XXX" in test data string)
- **Documentation TODOs**: References to TODO tracking system only
- **TODO tracking files**: 3 files (`dev/todos.md`, `todos.md`, `KNOWN_ISSUES.md`)
- **Existing GitHub issues**: 5 total (3 open, 2 closed)

**Summary**:
- Total actionable TODOs: 8 items (2 code + 6 from tracking files)
- Existing GitHub issues: 3 open (already tracked)
- Trivial fixes: 0 items
- Important (need new GitHub issues): 6 items
- Obsolete: 1 item
- By design: 7 items (document in architecture/contributing)

## Source Code TODOs

### src/finances/amazon/grouper.py

**Location**: Lines 91, 98

**Code**:
```python
# TODO(#15): Implement shipment-level grouping with domain models
# TODO(#15): Implement daily shipment-level grouping with domain models
```

**Analysis**:
- **Category**: Already tracked in GitHub
- **GitHub Issue**: #15 (CLOSED) - "Evaluate SHIPMENT and DAILY_SHIPMENT grouping levels - implement or remove?"
- **Status**: Issue closed - these grouping levels were evaluated and left as future enhancements
- **Action**: No action needed - TODOs properly reference closed issue

## Test Code TODOs

**Findings**: No actual TODOs in test code.

**False positive**:
- `tests/unit/test_apple/test_matcher.py:279` - Contains "XXX" as part of test data string
  `"order_id": "ZZ9YY8XXX"` - This is a mock order ID, not a TODO comment

**Action**: No action needed.

## Documentation TODOs

All TODO references in documentation are:
1. References to TODO tracking system in CLAUDE.md (PR success criteria)
2. References in this Phase 6 plan itself
3. No actionable TODOs found

**Action**: No action needed.

## Existing GitHub Issues

**Total Issues**: 5 (3 open, 2 closed)

### Open Issues (3)

**Issue #20**: Add pre-commit hook to prevent low-value test patterns
- **Status**: OPEN
- **Category**: Code quality / Testing
- **Relevance**: Maintenance enhancement
- **Action**: No action needed - already tracked

**Issue #19**: Fix YNAB category test data fixture missing category_group_id
- **Status**: OPEN
- **Category**: Testing / Bug fix
- **Relevance**: Test infrastructure improvement
- **Action**: No action needed - already tracked

**Issue #17**: Add validation logic for domain models
- **Status**: OPEN
- **Category**: Code quality / Domain models
- **Relevance**: Future enhancement for data validation
- **Action**: No action needed - already tracked

### Closed Issues (2)

**Issue #16**: Post-Phase 4.5: Minor code quality improvements
- **Status**: CLOSED
- **Category**: Code quality
- **Relevance**: Completed improvements
- **Action**: None - completed

**Issue #15**: Evaluate SHIPMENT and DAILY_SHIPMENT grouping levels - implement or remove?
- **Status**: CLOSED
- **Category**: Amazon matching architecture
- **Relevance**: Referenced by TODOs in src/finances/amazon/grouper.py (lines 91, 98)
- **Action**: None - evaluated and left as future enhancements

### Summary

All existing GitHub issues are properly tracked and categorized.
No conflicts with TODO tracking files.
Source code TODOs properly reference issue #15.

## TODO Tracking Files Analysis

### 1. dev/todos.md (10,020 bytes)

**Content Summary**:
- **Minor Items**: 6 items total
  - 3 completed (marked with [X])
  - 3 open items
- **Major Items**: 2 items total
  - 1 completed (data flow schemas - Phase 4.5)
  - 1 open item (Python version targeting)
- **Incomplete CLI Implementations**: All completed (marked with [X])
- **Architecture and Testing Refactoring**: 4 open items

**Open Items Categorized**:

#### Important (need GitHub issues): 4 items

1. **Fix potential data loss risk in retirement CLI** (lines 14-19)
   - Priority: Medium
   - Component: Retirement CLI
   - Issue: --output-file serves dual purpose (input/output), risk of overwrites
   - Recommendation: Add separate --input-file option
   - Context: PR #8 code review feedback

2. **Make cash flow analysis more lenient for test environments** (lines 20-24)
   - Priority: Low
   - Component: Cash flow analysis, E2E testing
   - Issue: Requires 6+ months data, excludes from E2E tests
   - Recommendation: Detect test environment or configurable minimum requirements
   - Context: PR #9 - excluded from test_flow_go_interactive_mode

3. **Improve flow_test_env synthetic test data for realistic matches** (lines 25-31)
   - Priority: Medium
   - Component: E2E testing, test fixtures
   - Issue: Independent generation means matchers find no matches in E2E tests
   - Recommendation: Generate coordinated test data with matching amounts/dates
   - Context: flow_test_env fixture

4. **Make --nodes-excluded not transitive** (lines 55-56)
   - Priority: Low
   - Component: Flow system
   - Issue: Transitive exclusion breaks usefulness in test scenarios
   - Recommendation: Either make non-transitive or add separate --nodes-skipped

#### By Design (document in architecture docs): 2 items

5. **Decentralize Flow Node Registration** (lines 118-136)
   - Status: Architectural improvement, not a bug
   - Priority: Post-Phase 1 refactoring
   - Current: Centralized in `setup_flow_nodes()` function
   - Proposed: Class-based approach with domain-specific `flow.py` modules
   - Action: Document as future enhancement, not urgent issue

6. **Consider Extracting HTML Parsing from email_fetcher.py** (lines 138-154)
   - Status: Architectural improvement, not a bug
   - Priority: Low - only if pain becomes significant
   - Current: IMAP fetch + HTML extraction in one module
   - Proposed: Separate extraction layer
   - Action: Document as future enhancement, not urgent issue

#### Obsolete: 2 items

7. **Figure out Python version targeting** (lines 53-54)
   - Analysis: README.md shows Python 3.13+ badge, pyproject.toml specifies `requires-python = ">=3.13"`
   - Action: Delete - already resolved

8. **Extract flow graph JSON serialization** (lines 112-113)
   - Analysis: Need to verify if this is still relevant or completed
   - Action: Review code and determine status

### 2. todos.md (2,026 bytes)

**Content Summary**:
Single future refactoring item - "Split Generation Flow - Domain Model Migration"

**Analysis**:
- **Status**: Planned refactoring
- **Priority**: Medium
- **Complexity**: Medium
- **Effort**: 4-6 hours
- **Category**: Important (needs GitHub issue)

**Item Details**:
- Component: YNAB split generation flow
- Issue: Flow node uses dict transformations instead of domain models
- Current: Split calculator uses `Money` type, but flow node uses dicts
- Goal: Update split generation flow to use domain models directly
  - `YnabTransaction` instead of dicts
  - `AppleReceipt`/`ParsedReceipt` instead of dicts
  - `AmazonOrderItem` instead of dicts
- Benefits: Type safety, eliminate manual transformations, consistency

**Action**: Create GitHub issue with maintenance template

### 3. KNOWN_ISSUES.md (2,811 bytes)

**Content Summary**:
Documents known limitations and issues.

**Analysis**: Most items are "by design" and should be migrated to architecture or contributing documentation,
  not GitHub issues.

**Sections**:

1. **Test Infrastructure** (lines 7-18)
   - E2E Test Subprocess Failures
   - Status: ✅ RESOLVED as of 2025-10-05
   - Action: Remove from KNOWN_ISSUES.md (already resolved)

2. **CLI Commands** (lines 20-39)
   - Incomplete error handling
   - Parameter validation gaps
   - Status: Low priority, documented behavior
   - Action: Delete section - these are acceptable limitations, not issues

3. **Flow System** (lines 41-49)
   - Change detection limitations (file-based, may miss content changes)
   - Status: Acceptable for current use case
   - Action: Document in ARCHITECTURE.md as design decision

4. **Data Processing** (lines 51-68)
   - Currency precision (integer arithmetic by design)
   - Multi-account Amazon support (manual account name detection)
   - Status: By design
   - Action: Document in ARCHITECTURE.md as design decisions

5. **Security & Privacy** (lines 70-87)
   - Test data must be synthetic
   - YNAB API tokens in .env
   - Status: Protected by code review and .gitignore
   - Action: Document in CONTRIBUTING.md security section

## Categorized TODO Summary

### Trivial (fix immediately): 0 items

None identified.

### Important (create GitHub issues): 6 items

1. Fix potential data loss risk in retirement CLI non-interactive mode
2. Make cash flow analysis more lenient for test environments
3. Improve flow_test_env synthetic test data for realistic matches
4. Make --nodes-excluded not transitive in flow system
5. Split Generation Flow - Domain Model Migration (from todos.md)
6. Verify flow graph JSON serialization extraction status (pending review)

### Obsolete (delete): 1 item

1. Python version targeting (already resolved - Python 3.13+ specified)

### By Design (document in architecture/contributing): 7 items

1. Decentralize Flow Node Registration (future refactoring)
2. Extract HTML Parsing from email_fetcher.py (future refactoring)
3. Flow system change detection limitations
4. Currency precision using integer arithmetic
5. Multi-account Amazon support format
6. Test data must be synthetic
7. YNAB API tokens in .env

## Documentation Gaps Revealed

Based on TODO audit, the following gaps exist in documentation:

1. **Architecture documentation missing**:
   - Flow node registration architecture (centralized approach)
   - Change detection mechanism (file-based timestamps)
   - Currency handling design (integer-only arithmetic)
   - Multi-account support patterns

2. **Contributing documentation missing**:
   - Security guidelines (synthetic test data, credential management)
   - Future refactoring opportunities (flow node decentralization, HTML extraction)

3. **Testing documentation gaps**:
   - E2E test data coordination patterns
   - Cash flow analysis test data requirements
   - Flow system testing strategies

## Recommendations

### Phase 3, Task 5 Actions (TODO Cleanup and GitHub Infrastructure)

**Create GitHub issues for** (6 issues):
1. ✅ Retirement CLI: Fix potential data loss risk in non-interactive mode (#21)
2. ✅ Cash flow: Make analysis more lenient for test environments (#22)
3. ✅ Testing: Improve flow_test_env synthetic test data coordination (#23)
4. ✅ Flow system: Make --nodes-excluded not transitive (#24)
5. ✅ YNAB: Split Generation Flow domain model migration (#25)
6. ✅ Flow system: Verify/resolve flow graph JSON serialization extraction (#26)

**Delete TODOs** (1 item):
1. Python version targeting (resolved)

**Document in architecture** (4 items):
1. Flow node registration architecture
2. Change detection mechanism
3. Currency handling design
4. Multi-account support patterns

**Document in contributing** (3 items):
1. Security guidelines (synthetic data, credentials)
2. Future refactoring opportunities
3. Testing data coordination patterns

**Delete files** (as planned in Task 5):
1. `dev/todos.md` - All items migrated to GitHub issues or documentation
2. `todos.md` - All items migrated to GitHub issues
3. `KNOWN_ISSUES.md` - All items migrated to architecture/contributing docs

## Next Steps

1. **Task 2**: Complete specification and documentation audit
2. **Review findings**: Ensure categorization is accurate
3. **Task 3**: Create ARCHITECTURE.md with design decisions from "by design" items
4. **Task 4**: Enhance CONTRIBUTING.md with security and testing guidelines
5. **Task 5**: Create 6 GitHub issues with maintenance template
6. **Task 5**: Delete obsolete TODO and migrate content
7. **Task 5**: Delete 3 TODO tracking files after migration complete

---

**Audit Completed**: 2025-10-18
**Next Task**: Task 2 - Specification and Documentation Audit

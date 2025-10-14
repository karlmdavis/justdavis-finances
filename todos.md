# TODO List

## Future Refactoring

### Split Generation Flow - Domain Model Migration

**Status:** Planned
**Priority:** Medium
**Complexity:** Medium

**Context:**
The split generation flow (`src/finances/ynab/split_generation_flow.py`) currently works with dict-based data structures rather than domain models.
While the underlying split calculator has been updated to use the `Money` type, the flow node itself still performs manual transformations between parser formats and calculator formats.

**Current State:**
- Split calculator (`split_calculator.py`) uses `Money` type ✅
- Flow node uses dict transformations for Apple receipts ❌
- Flow node uses dict transformations for Amazon orders ❌
- Transform functions manually map between formats ❌

**Goals:**
1. Update split generation flow to use domain models directly:
   - `YnabTransaction` instead of transaction dicts
   - `AppleReceipt` / `ParsedReceipt` instead of receipt dicts
   - `AmazonOrderItem` instead of order dicts
2. Eliminate transform functions (`transform_apple_receipt_data`, `transform_amazon_order_data`)
3. Update split calculator functions to accept domain models
4. Simplify data flow between matching and split generation

**Benefits:**
- Type safety across the entire split generation pipeline
- Elimination of manual dict transformations
- Consistency with rest of codebase (Amazon/Apple/YNAB all use domain models)
- Easier maintenance and testing

**Implementation Approach:**
1. Update `calculate_apple_splits()` signature to accept `ParsedReceipt` and `YnabTransaction`
2. Update `calculate_amazon_splits()` signature to accept `list[AmazonOrderItem]` and `YnabTransaction`
3. Remove transform functions from split generation flow
4. Update split generation flow to load and pass domain models directly
5. Update tests to use domain models

**Related Work:**
- Phase 4 domain model migrations (completed)
- Apple parser `to_dict()` fix (completed)
- YNAB loader deprecation cleanup (completed)

**Estimated Effort:** 4-6 hours

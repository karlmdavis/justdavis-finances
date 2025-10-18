# YNAB Transaction Updater - Product Specification

## Executive Summary

The YNAB Transaction Updater automates the application of Amazon and Apple transaction matching
  results to YNAB transactions.
It splits consolidated transactions into detailed subtransactions with item-level memos,
  providing visibility into individual purchases while maintaining transaction integrity.
The system employs a three-phase safety approach (generate → review → apply) to prevent
  accidental data corruption and ensures all operations are reversible.

## Problem Statement

### Current Pain Points
1. **Opaque Transaction Details**: Amazon and Apple transactions appear as single line items
     (e.g., "AMZN Mktp US*RT4Y12" for $89.99) without visibility into what was actually
     purchased.
2. **Manual Splitting Burden**: Users must manually split transactions and add item details,
     taking 5-10 minutes per transaction.
3. **Lost Purchase History**: Without item-level detail, historical spending analysis is
     impossible.
4. **Error-Prone Process**: Manual data entry leads to mistakes and inconsistencies.
5. **Tax/Shipping Ambiguity**: Difficult to allocate tax and shipping costs across items
     manually.

### Business Impact
- **Time Cost**: 10+ minutes per multi-item transaction for manual splitting.
- **Data Quality**: Inconsistent memo formats and missing details.
- **Analysis Limitations**: Cannot track spending on specific products or categories.
- **Budget Accuracy**: Inability to understand true cost allocation.

## Solution Overview

An automated system that:
1. Reads transaction matching results from Amazon/Apple matchers.
2. Generates a reviewable mutation plan with proposed splits.
3. Allows user review and selective approval.
4. Applies approved changes via the YNAB CLI.
5. Maintains a complete audit trail for recovery.

### Key Principles
- **Safety First**: Three-phase approach with user review.
- **Cache-Only**: Works only with cached YNAB data (no live API calls).
- **No Category Changes**: Focus on splits and memos only.
- **Integer Arithmetic**: All calculations in milliunits to avoid floating-point errors.
- **Reversibility**: Complete audit trail via delete logs.

## Functional Requirements

### Input Requirements

#### Match Results Data
- **Source**: JSON files from Amazon/Apple transaction matchers
- **Required Fields**:
  - Transaction ID.
  - Match confidence.
  - Order/receipt details with items.
  - Item names, quantities, amounts.
  - Tax and shipping information (where available).

#### YNAB Cache Data
- **Source**: Cached `transactions.json` from YNAB data workflow
- **Required Fields**:
  - Transaction ID, date, amount.
  - Current memo, payee, category.
  - Account information.
  - Existing subtransactions (if any).

### Processing Requirements

#### Phase 1: Mutation Generation
1. Load match results and YNAB cache
2. Apply optional filtering (--unapproved-only flag):
   - Filter YNAB transactions to only unapproved (approved=false)
   - Skip transactions with approved=true or missing approved field
3. For each matched transaction:
   - Skip if confidence below threshold
   - Skip if already split correctly
   - Skip if transaction is approved (when using --unapproved-only)
   - Calculate split amounts with tax/shipping
   - Generate mutation record
4. Output YAML mutation plan with filtering statistics

#### Phase 2: User Review
1. Display proposed mutations in readable format
2. Show before/after comparison
3. Allow individual approval/rejection
4. Export approved mutations to new file

#### Phase 3: Application
1. Verify pre-conditions still valid
2. For each approved mutation:
   - Execute via YNAB CLI
   - Log any deletions
   - Verify success
3. Generate summary report

### Output Requirements

#### YAML Mutation Plan
- Human-readable format
- Complete transaction context
- Detailed split specifications
- Reversibility information

#### Delete Log
- NDJSON format for recovery
- Complete transaction data before deletion
- Command used for deletion
- Timestamp and context

## Technical Architecture

### Tax & Shipping Allocation Strategy

#### Amazon Transactions
Amazon provides item-level totals in the `Total Owed` field that already includes tax and shipping allocated to each item. No additional calculation needed.

```python
# Amazon item processing (simplified)
for item in order['items']:
    amount_cents = item['amount']  # Already includes tax/shipping
    splits.append({
        'amount': -amount_cents * 10,  # Convert to milliunits
        'memo': f"{item['name']} ({item['quantity']}x @ ${item['unit_price']:.2f})"
    })
```

#### Apple Transactions
Apple provides receipt-level tax that must be allocated proportionally across items.

```python
def allocate_apple_tax(items, subtotal, tax, total_milliunits):
    """
    Allocate tax proportionally across items using integer arithmetic.

    Args:
        items: List of receipt items with 'cost' field
        subtotal: Receipt subtotal in dollars
        tax: Receipt tax in dollars
        total_milliunits: Transaction total in milliunits (negative)

    Returns:
        List of split dictionaries with amount and memo
    """
    # Convert to milliunits
    subtotal_milliunits = int(subtotal * 1000)
    tax_milliunits = int(tax * 1000)

    # Sort items for stable ordering
    sorted_items = sorted(items, key=lambda x: (-x['cost'], x['title']))

    splits = []
    allocated = 0

    # Allocate proportionally to all items except last
    for item in sorted_items[:-1]:
        item_base = int(item['cost'] * 1000)
        item_tax = (item_base * tax_milliunits) // subtotal_milliunits
        item_total = item_base + item_tax

        splits.append({
            'amount': -item_total,  # Negative for expense
            'memo': f"{item['title']} (incl. tax)"
        })
        allocated += item_total

    # Last item gets remainder to ensure exact sum
    last_item_amount = abs(total_milliunits) - allocated
    splits.append({
        'amount': -last_item_amount,
        'memo': f"{sorted_items[-1]['title']} (incl. tax)"
    })

    return splits
```

### Split Calculation Rules

1. **Integer Arithmetic Only**: All calculations in milliunits (1000 = $1.00)
2. **Stable Sort Order**: Items sorted by amount DESC, then by name
3. **Remainder Allocation**: Last item receives any remainder from rounding
4. **Sum Verification**: Assert splits sum exactly to transaction total
5. **Single Items**: No split needed, only memo update

### Command-Line Interface

The YNAB Transaction Updater is integrated into the Financial Flow System as part of the
  split generation workflow.

```bash
# Execute the complete financial flow
finances flow

# The flow system automatically:
# 1. Syncs YNAB data (YnabDataNode)
# 2. Matches Amazon transactions (AmazonMatcherNode)
# 3. Matches Apple transactions (AppleMatcherNode)
# 4. Generates split edits from matches (embedded in matcher nodes)
# 5. Runs cash flow analysis (CashFlowNode)

# Split generation happens automatically during matching
# Output: data/{amazon,apple}/split_edits/YYYY-MM-DD_HH-MM-SS_split_edits.json
```

**Note**: The three-phase workflow (generate → review → apply) is currently in planning.
Current implementation generates split edit files that can be manually reviewed and applied via the
  YNAB CLI.

**Flow System Integration:**
- Split calculation embedded in Amazon and Apple matcher nodes.
- Uses domain models (YnabSplit, TransactionSplitEdit, SplitEditBatch).
- Outputs JSON files with complete split specifications.
- Configuration via environment variables or `.env` file.

### Safety Features

#### Pre-condition Verification
- Transaction amount unchanged
- Transaction still exists
- Not already split (unless force flag)
- Match confidence above threshold

#### Atomic Operations
- Each transaction processed independently
- Failure of one doesn't affect others
- State verified before each operation

#### Audit Trail
- Delete log in NDJSON format
- Each entry contains full transaction data
- Recovery instructions included
- Timestamps for all operations

#### Dry-Run Mode
- Complete simulation without changes
- Uses `ynab --dry-run` flag
- Validates all operations
- Reports what would happen

## Data Formats

### YAML Mutation Plan Format

```yaml
metadata:
  generated_at: "2025-09-20T14:30:00Z"
  source_file: "results/2025-09-01_amazon_matching_results.json"
  total_mutations: 42
  total_amount: -4523.67

mutations:
  - transaction_id: "abc-123-def"
    action: split
    confidence: 0.95
    source: amazon
    account: "Chase Credit Card"
    date: "2025-09-15"
    original:
      amount: -89990  # milliunits
      memo: "AMZN Mktp US*RT4Y12"
      payee: "Amazon.com"
    matched_order:
      order_id: "111-2223334-5556667"
      order_date: "2025-09-14"
      account: "erica"
    splits:
      - amount: -45990
        memo: "Echo Dot (4th Gen) - Charcoal (1x @ $45.99)"
      - amount: -23500
        memo: "USB-C Cable 6ft - 2 Pack (1x @ $23.50)"
      - amount: -15990
        memo: "Phone Case Clear (1x @ $15.99)"
      - amount: -4510
        memo: "Screen Protector (1x @ $4.51)"

  - transaction_id: "xyz-789-ghi"
    action: split
    confidence: 1.0
    source: apple
    account: "Apple Card"
    date: "2025-09-16"
    original:
      amount: -32970  # milliunits
      memo: "Apple Services"
      payee: "Apple.com"
    matched_receipt:
      order_id: "ML7PQ2XYZ"
      receipt_date: "2025-09-16"
      apple_id: "user@example.com"
      subtotal: 29.99
      tax: 2.98
    splits:
      - amount: -21980  # Proportional tax included
        memo: "Logic Pro (incl. tax)"
      - amount: -10990  # Remainder to ensure exact sum
        memo: "Final Cut Pro (incl. tax)"

  - transaction_id: "mno-456-pqr"
    action: update_memo
    confidence: 0.92
    source: amazon
    reason: "Single item - no split needed"
    original:
      amount: -1999
      memo: "AMZN DIGIT"
    new_memo: "Kindle Book: 'Project Hail Mary' by Andy Weir"
```

### Delete Log Format (NDJSON)

```json
{"timestamp":"2025-09-20T14:35:22Z","action":"delete_for_recreate","transaction_id":"abc-123-def","budget_id":"last-used","command":"ynab update transaction --id abc-123-def --split ...","original_data":{"id":"abc-123-def","date":"2025-09-15","amount":-89990,"payee_name":"Amazon.com","account_name":"Chase Credit Card","memo":"AMZN Mktp US*RT4Y12","subtransactions":[]}}
{"timestamp":"2025-09-20T14:35:23Z","action":"created","transaction_id":"new-id-123","budget_id":"last-used","parent_transaction":"abc-123-def","splits":4}
```

### Approval File Format

```yaml
metadata:
  reviewed_at: "2025-09-20T14:45:00Z"
  reviewer: "user"
  source_mutations: "mutations.yaml"

approved:
  - transaction_id: "abc-123-def"
    approved: true
    notes: "Verified against Amazon order email"

  - transaction_id: "xyz-789-ghi"
    approved: true

  - transaction_id: "mno-456-pqr"
    approved: false
    reason: "Incorrect item - was actually different book"

summary:
  total_reviewed: 3
  approved: 2
  rejected: 1
  approved_amount: -122960
```

## Testing Strategy

### Synthetic Test Data

#### Test Fixture Generator
```python
def generate_test_transaction(amount, memo, date=None):
    """Generate synthetic YNAB transaction."""
    return {
        'id': str(uuid.uuid4()),
        'date': date or '2025-09-20',
        'amount': amount,
        'payee_name': 'Test Payee',
        'account_name': 'Test Account',
        'memo': memo,
        'category_name': 'Shopping',
        'subtransactions': []
    }

def generate_amazon_match(transaction_id, items):
    """Generate synthetic Amazon match result."""
    return {
        'ynab_transaction': {'id': transaction_id},
        'matched': True,
        'amazon_orders': [{
            'order_id': '111-' + str(random.randint(1000000, 9999999)),
            'items': items,
            'total': sum(item['amount'] for item in items)
        }],
        'confidence': 0.95
    }
```

### Test Scenarios

#### Basic Tests
1. **Single Item**: No split, only memo update
2. **Two Items**: Even split, no remainder
3. **Three Items**: Uneven split with remainder
4. **Many Items**: 10+ items with varied amounts

#### Tax Allocation Tests
1. **Apple with Tax**: Proportional allocation
2. **Apple No Tax**: Items at face value
3. **Large Tax**: Tax exceeds smallest item value
4. **Rounding**: Verify remainder handling

#### Approval Status Filtering Tests
1. **All Transactions**: Default behavior (no filtering)
2. **Unapproved Only**: Filter to approved=false transactions only
3. **Mixed Status Dataset**: Verify correct filtering with mixed approved/unapproved
4. **Missing Approved Field**: Default to approved=true when field absent
5. **Invalid Approved Values**: Handle non-boolean values gracefully

#### Edge Cases
1. **Zero Amount Item**: Free item in order
2. **Negative Amount**: Refund/credit
3. **Already Split**: Skip or force update
4. **Low Confidence**: Below threshold
5. **Missing Data**: Incomplete match result
6. **All Approved**: No mutations when all transactions approved
7. **All Unapproved**: Process all when none approved

#### Integration Tests
1. **Dry Run**: Verify no changes made
2. **CLI Interaction**: Test with actual `ynab --dry-run`
3. **Delete/Recreate**: Verify split modification flow
4. **Error Recovery**: Simulate failures

### Test Execution

```bash
# Run unit tests
pytest tests/test_split_calculator.py -v
pytest tests/test_mutation_generator.py -v
pytest tests/test_tax_allocation.py -v

# Run integration tests with dry-run
pytest tests/test_integration.py --dry-run -v

# Run full test suite
pytest --cov=. --cov-report=html
```

### Test Coverage Requirements
- Unit test coverage: ≥95%
- Integration test coverage: ≥85%
- Edge case coverage: 100%
- No production data modifications

## Implementation Checklist

### Phase 1: Core Components
- [ ] Split calculator with integer arithmetic
- [ ] Tax allocation algorithm
- [ ] YAML mutation generator
- [ ] Match result parser

### Phase 2: User Interface
- [ ] Mutation review interface
- [ ] Approval workflow
- [ ] Diff visualization
- [ ] Summary statistics

### Phase 3: YNAB Integration
- [ ] CLI command builder
- [ ] Delete log writer
- [ ] Pre-condition verifier
- [ ] Dry-run simulator

### Phase 4: Testing
- [ ] Synthetic data generators
- [ ] Unit test suite
- [ ] Integration tests
- [ ] Edge case tests

### Phase 5: Documentation
- [ ] User guide
- [ ] Recovery procedures
- [ ] API documentation
- [ ] Example workflows

## Success Criteria

### Functional Success
- ✓ Correctly splits 100% of test transactions
- ✓ Tax allocation matches manual calculation within 1¢
- ✓ All splits sum exactly to transaction total
- ✓ Memos contain accurate item information

### Safety Success
- ✓ Zero unintended data modifications
- ✓ Complete audit trail for all changes
- ✓ Successful recovery from all test failures
- ✓ User approval required for all mutations

### Performance Success
- ✓ Process 1000 transactions in <10 seconds
- ✓ Generate mutations for month of data in <5 seconds
- ✓ Interactive review responds in <100ms

### Quality Success
- ✓ 95%+ test coverage
- ✓ Zero production incidents
- ✓ Deterministic/reproducible results
- ✓ Clear error messages

## Risk Mitigation

### Data Integrity Risks
- **Risk**: Accidental deletion of transactions
- **Mitigation**: Delete log, dry-run mode, pre-condition checks

### Calculation Risks
- **Risk**: Rounding errors in splits
- **Mitigation**: Integer arithmetic, remainder allocation, sum verification

### User Error Risks
- **Risk**: Approving incorrect mutations
- **Mitigation**: Clear diffs, detailed previews, reversibility

### Integration Risks
- **Risk**: YNAB API/CLI changes
- **Mitigation**: Version pinning, compatibility tests, abstraction layer

## Future Enhancements

### Near-Term (v2.0)
- Category assignment based on item types
- Bulk approval with filters
- Scheduled/automated runs
- Email notifications

### Medium-Term (v3.0)
- Machine learning for category prediction
- Receipt attachment integration
- Multi-user support
- Web interface

### Long-Term (v4.0)
- Real-time processing
- Direct YNAB API integration
- Mobile app
- Analytics dashboard

## Appendix: Example Workflows

### Typical Monthly Workflow

```bash
# 1. Execute the financial flow system
finances flow

# The flow prompts for each step:
# - Update YNAB data? (y/n)
# - Run Amazon matching? (y/n)
# - Run Apple matching? (y/n)
# - Generate cash flow analysis? (y/n)

# 2. Review generated split edits
ls data/amazon/split_edits/
ls data/apple/split_edits/

# Example output:
# data/amazon/split_edits/2025-09-30_15-30-45_split_edits.json
# data/apple/split_edits/2025-09-30_15-31-12_split_edits.json

# 3. Review split edit files (JSON format)
cat data/amazon/split_edits/2025-09-30_15-30-45_split_edits.json | jq '.metadata'
cat data/amazon/split_edits/2025-09-30_15-30-45_split_edits.json | jq '.edits[] | .transaction_id'

# 4. Apply edits manually via YNAB CLI (three-phase workflow planned for future)
# Current state: Manual application required
# Future state: Automated review and application via finances CLI
```

### Current Limitations

**Three-Phase Workflow Status:**
The three-phase workflow (generate → review → apply) described in this specification is
  **planned for future implementation**.

**Current Implementation:**
- Split edit generation: ✅ Implemented (embedded in matcher nodes)
- Review interface: ❌ Not yet implemented
- Automated application: ❌ Not yet implemented

**Manual Workaround:**
Users can manually review split edit JSON files and apply changes via the YNAB CLI or web interface.

**Future Development:**
A dedicated `finances splits` command will provide:
- Interactive review of generated split edits
- Approval workflow with confidence thresholds
- Automated application via YNAB CLI
- Complete audit trail and reversibility

---

## Document History

- **2025-09-20**: Initial specification created
- **2025-09-20**: Added unapproved transaction filtering feature
- **Version**: 1.1
- **Status**: Enhanced with Filtering Feature
- **Owner**: Karl Davis

---

This specification provides a complete blueprint for safely and accurately applying Amazon and Apple transaction matching results to YNAB transactions with full reversibility and user control.

# Development TODOs

## Amazon Transaction Matching

### Remove Fuzzy Matching Strategy
**Priority**: Medium
**Impact**: Improve matching accuracy and reduce false positives

Currently, the Amazon transaction matching system includes fuzzy matching strategies (`fuzzy_order_match` and `fuzzy_shipment_match`) that allow for price tolerance when exact matches aren't found. Analysis shows:

- Only 1.3% of matches use fuzzy strategies (7 out of 552 matches)
- These have low confidence scores (0.62-0.77)
- They allow significant price differences (up to ~20% or $2-3)
- May create false positive matches

**Task**: Remove or disable fuzzy matching strategies and require exact penny-perfect matches only.

**Affected Strategies to Remove**:
- `fuzzy_order_match`
- `fuzzy_shipment_match`

**Example Transactions Using Fuzzy Matching** (for testing after removal):

1. **Lowest Confidence Cases**:
   - YNAB: `8ed1124b-c98a-40ee-b3c9-508174bdfcc7` (2024-12-04, $3.70)
     - Amazon Order: `113-3123407-2854602`
     - Confidence: 0.62 (fuzzy_order_match)

   - YNAB: `528a943e-d2b4-4728-a63d-caa2bf17d007` (2024-11-09, $8.20)
     - Amazon Order: `114-2643502-9816245`
     - Confidence: 0.64 (fuzzy_shipment_match)

2. **Recurring Problem Order** (multiple fuzzy matches):
   - Amazon Order: `111-2150717-4161061` matches multiple YNAB transactions:
     - `30064272-5e48-473c-9c53-590a46ce27d6` (2024-03-26, $12.15, conf: 0.70)
     - `92452fda-1d85-467d-88a7-ff7e2398e413` (2024-03-25, $8.46, conf: 0.77)
     - `2a366ec0-c287-4a9a-b357-3f810cfc3242` (2024-03-28, $13.76, conf: 0.73)
     - `bcdd895d-61ff-4acc-bd46-562e3351aa02` (2024-03-24, $8.47)

3. **Other Test Cases**:
   - YNAB: `6b2bcbe4-77a4-4b54-9413-617b42bd8b5d` (2024-04-21, $12.71)
     - Amazon Order: `114-7275625-8053031`
     - Confidence: 0.75 (fuzzy_shipment_match)

   - YNAB: `62320508-9379-48fa-b529-645ff83560d8` (2025-06-08, $92.11)
     - Amazon Order: `111-5264356-9196252`
     - Confidence: 0.75 (fuzzy_order_match)

**Implementation Notes**:
- After removal, these 7 transactions will become unmatched
- This is acceptable as it's better to have no match than a potentially incorrect match
- The remaining 545 transactions (98.7%) will be unaffected as they use exact matching strategies
- Consider adding better logging for unmatched transactions to help identify why matches fail

**Files to Modify**:
- `analysis/amazon_transaction_matching/simplified_matcher.py` (remove fuzzy strategies)
- `analysis/amazon_transaction_matching/match_transactions_batch.py` (update strategy list)
- Related test files

---

### Improve Confidence Scoring for Amount Deltas
**Priority**: Medium
**Impact**: Better confidence scores for transaction matches with amount discrepancies

Currently, Amazon transaction matches can have high confidence scores (0.98) even when there are significant amount deltas between the YNAB transaction and Amazon order totals. This can lead to questionable matches being approved.

**Problem Examples**:
1. **Large Amount Delta**:
   - YNAB TX: `922ed3c6-c751-4837-804b-8b1d0b7ce1c5` ($7.41)
   - Amazon Order: `111-1506027-7306632` ($6.88)
   - Amount Delta: $0.53 (7.2%)
   - Current Confidence: 0.98 (should be much lower)

2. **Even 1-Cent Deltas Get Perfect Confidence**:
   - YNAB TX: `fe2f97eb-4251-43fb-95f9-584994307e9f` ($17.67)
   - Amazon Order: `111-6883526-4527447` ($17.66)
   - Amount Delta: $0.01 (0.1%)
   - Current Confidence: 1.00 (should be slightly reduced)

**Task**: Implement confidence penalties for amount deltas in the matching scorer.

**Proposed Penalty Logic**:
- **Perfect match** (0 cents delta): No penalty
- **1 cent delta**: Small but meaningful penalty (-0.02 to -0.05)
- **2-3 cents delta**: Minor penalty (-0.05 to -0.10)
- **4-10 cents delta**: Moderate penalty (-0.15 to -0.30)
- **>10 cents delta**: Heavy penalty (-0.40 to -0.60)
- **>5% delta**: Additional percentage-based penalty

**Rationale**: Even 1-cent differences indicate imperfect matching (rounding errors, tax allocation differences, etc.) and should never receive perfect confidence scores.

**Files to Modify**:
- `analysis/amazon_transaction_matching/match_scorer.py` (add amount delta penalty logic)
- Consider percentage-based penalties for larger transactions
- Ensure fuzzy matching strategies still work but with appropriate confidence reduction

**Expected Outcome**:
- Matches with significant amount deltas receive appropriately lower confidence scores
- Reduces false positives in mutation generation (confidence threshold filtering)
- Maintains high confidence only for truly accurate matches

---

## Future Tasks

(Add more tasks here as they come up)
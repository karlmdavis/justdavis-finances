#!/usr/bin/env python3
"""
Apple Transaction Matching Module

Core logic for matching Apple receipts to YNAB transactions.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class MatchStrategy(Enum):
    """Different matching strategies"""
    EXACT_MATCH = "exact_date_amount"
    DATE_WINDOW = "date_window_match"


@dataclass
class MatchResult:
    """Result of a matching operation"""
    ynab_transaction: Dict[str, Any]
    matched: bool
    apple_receipts: List[Dict[str, Any]]
    match_confidence: float
    match_strategy: Optional[MatchStrategy]
    unmatched_amount: float = 0.0
    match_details: Dict[str, Any] = None


class AppleMatcher:
    """Core Apple receipt to YNAB transaction matcher"""
    
    def __init__(self, date_window_days: int = 2):
        """
        Initialize the matcher.

        Args:
            date_window_days: Number of days to search before/after transaction date
        """
        self.date_window_days = date_window_days
    
    def match_single_transaction(self, 
                                ynab_transaction: Dict[str, Any], 
                                apple_receipts_df: pd.DataFrame) -> MatchResult:
        """
        Match a single YNAB transaction to Apple receipts.
        
        Args:
            ynab_transaction: YNAB transaction data (normalized)
            apple_receipts_df: DataFrame of Apple receipts
            
        Returns:
            MatchResult with details of the match
        """
        # Extract transaction details
        tx_date = ynab_transaction['date']
        tx_amount = ynab_transaction['amount_dollars']
        tx_id = ynab_transaction['transaction_id']
        
        print(f"Matching transaction {tx_id}: ${tx_amount:.2f} on {tx_date.strftime('%Y-%m-%d')}")
        
        # Strategy 1: Exact Date and Amount Match
        exact_match = self._find_exact_match(tx_date, tx_amount, apple_receipts_df)
        if exact_match:
            return MatchResult(
                ynab_transaction=ynab_transaction,
                matched=True,
                apple_receipts=[exact_match],
                match_confidence=self._calculate_confidence(tx_amount, exact_match['total'], 0),
                match_strategy=MatchStrategy.EXACT_MATCH,
                match_details={"strategy": "exact_date_amount", "date_diff_days": 0}
            )
        
        # Strategy 2: Date Window Match
        window_match, date_diff = self._find_date_window_match(tx_date, tx_amount, apple_receipts_df)
        if window_match:
            return MatchResult(
                ynab_transaction=ynab_transaction,
                matched=True,
                apple_receipts=[window_match],
                match_confidence=self._calculate_confidence(tx_amount, window_match['total'], date_diff),
                match_strategy=MatchStrategy.DATE_WINDOW,
                match_details={"strategy": "date_window", "date_diff_days": date_diff}
            )
        
        # No match found
        return MatchResult(
            ynab_transaction=ynab_transaction,
            matched=False,
            apple_receipts=[],
            match_confidence=0.0,
            match_strategy=None,
            unmatched_amount=tx_amount,
            match_details={"strategy": "no_match", "reason": "no_matching_receipts_found"}
        )
    
    def _find_exact_match(self, 
                         tx_date: datetime, 
                         tx_amount: float, 
                         receipts_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Find receipts that match exactly on date and amount.
        
        Args:
            tx_date: Transaction date
            tx_amount: Transaction amount in dollars
            receipts_df: DataFrame of Apple receipts
            
        Returns:
            Matching receipt dictionary or None
        """
        if receipts_df.empty:
            return None
            
        # Filter to same date
        same_date_mask = receipts_df['receipt_date'].dt.date == tx_date.date()
        same_date_receipts = receipts_df[same_date_mask]
        
        if same_date_receipts.empty:
            return None
            
        # Find exact amount matches
        for _, receipt in same_date_receipts.iterrows():
            if receipt['total'] == tx_amount:
                print(f"  Found exact match: Receipt {receipt['order_id']} for ${receipt['total']:.2f}")
                return receipt.to_dict()
        
        return None
    
    def _find_date_window_match(self, 
                               tx_date: datetime, 
                               tx_amount: float, 
                               receipts_df: pd.DataFrame) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Find receipts within the date window that match the amount.
        
        Args:
            tx_date: Transaction date
            tx_amount: Transaction amount in dollars
            receipts_df: DataFrame of Apple receipts
            
        Returns:
            Tuple of (matching receipt dictionary or None, date difference in days)
        """
        if receipts_df.empty:
            return None, 0
            
        # Define date window
        start_date = tx_date - timedelta(days=self.date_window_days)
        end_date = tx_date + timedelta(days=self.date_window_days)
        
        # Filter to date window
        date_mask = (receipts_df['receipt_date'] >= start_date) & (receipts_df['receipt_date'] <= end_date)
        window_receipts = receipts_df[date_mask]
        
        if window_receipts.empty:
            return None, 0
            
        # Find amount matches, prioritizing closer dates
        best_match = None
        best_date_diff = float('inf')
        
        for _, receipt in window_receipts.iterrows():
            if receipt['total'] == tx_amount:
                date_diff = abs((receipt['receipt_date'] - tx_date).days)
                if date_diff < best_date_diff:
                    best_match = receipt.to_dict()
                    best_date_diff = date_diff
        
        if best_match:
            print(f"  Found date window match: Receipt {best_match['order_id']} for ${best_match['total']:.2f}, {best_date_diff} days off")
            return best_match, best_date_diff
            
        return None, 0
    
    def _calculate_confidence(self, 
                            ynab_amount: float, 
                            apple_amount: float, 
                            date_diff_days: int) -> float:
        """
        Calculate confidence score for a match.
        
        Args:
            ynab_amount: YNAB transaction amount
            apple_amount: Apple receipt amount
            date_diff_days: Difference in days between transaction and receipt
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 1.0
        
        # Amount matching penalty (now only exact matches are allowed)
        amount_diff = abs(ynab_amount - apple_amount)
        amount_penalty = 0 if amount_diff == 0 else 1.0  # No tolerance for amount differences
        
        # Date matching penalty
        date_penalty = min(0.3, date_diff_days * 0.15)
        
        # Calculate final confidence
        confidence = max(0, confidence - amount_penalty - date_penalty)
        
        # Boost for exact amount match despite date difference
        if amount_diff == 0 and date_diff_days <= 2:
            confidence = max(confidence, 0.85)
        
        return round(confidence, 2)


def batch_match_transactions(ynab_transactions_df: pd.DataFrame, 
                           apple_receipts_df: pd.DataFrame,
                           matcher: Optional[AppleMatcher] = None) -> List[MatchResult]:
    """
    Match a batch of YNAB transactions to Apple receipts.
    
    Args:
        ynab_transactions_df: DataFrame of YNAB transactions
        apple_receipts_df: DataFrame of Apple receipts  
        matcher: Optional AppleMatcher instance
        
    Returns:
        List of MatchResult objects
    """
    if matcher is None:
        matcher = AppleMatcher()
        
    results = []
    
    print(f"Matching {len(ynab_transactions_df)} YNAB transactions to {len(apple_receipts_df)} Apple receipts")
    
    for _, transaction in ynab_transactions_df.iterrows():
        tx_dict = transaction.to_dict()
        result = matcher.match_single_transaction(tx_dict, apple_receipts_df)
        results.append(result)
    
    return results


def generate_match_summary(results: List[MatchResult]) -> Dict[str, Any]:
    """
    Generate summary statistics for match results.
    
    Args:
        results: List of MatchResult objects
        
    Returns:
        Dictionary with summary statistics
    """
    total_transactions = len(results)
    matched_transactions = sum(1 for r in results if r.matched)
    
    if total_transactions == 0:
        return {"total_transactions": 0}
    
    # Calculate amounts
    total_amount = sum(r.ynab_transaction['amount_dollars'] for r in results)
    matched_amount = sum(r.ynab_transaction['amount_dollars'] for r in results if r.matched)
    unmatched_amount = total_amount - matched_amount
    
    # Confidence statistics
    matched_confidences = [r.match_confidence for r in results if r.matched]
    avg_confidence = sum(matched_confidences) / len(matched_confidences) if matched_confidences else 0
    
    # Strategy breakdown
    strategy_counts = {}
    for result in results:
        if result.match_strategy:
            strategy_name = result.match_strategy.value
            strategy_counts[strategy_name] = strategy_counts.get(strategy_name, 0) + 1
    
    summary = {
        "total_transactions": total_transactions,
        "matched": matched_transactions,
        "unmatched": total_transactions - matched_transactions,
        "match_rate": matched_transactions / total_transactions if total_transactions > 0 else 0,
        "average_confidence": round(avg_confidence, 3),
        "total_amount_matched": round(matched_amount, 2),
        "total_amount_unmatched": round(unmatched_amount, 2),
        "strategy_breakdown": strategy_counts
    }
    
    return summary


if __name__ == "__main__":
    # Test the matcher with sample data
    print("Apple Matcher test - this would require actual data to run")
    print("Use match_single_transaction.py or match_transactions_batch.py for actual matching")
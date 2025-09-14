#!/usr/bin/env python3
"""
Apple Match Scoring System

Confidence calculation logic specifically for Apple receipt to YNAB transaction matching.
Adapted from the Amazon matching system but simplified for Apple's direct transaction model.
"""

from datetime import date, datetime
from typing import Dict, Any, Optional
from enum import Enum


class AppleMatchType(Enum):
    """Types of Apple matches for scoring"""
    EXACT_MATCH = "exact_match"          # Same day, exact amount
    DATE_WINDOW = "date_window"          # Close date, exact amount
    AMOUNT_TOLERANCE = "amount_tolerance" # Exact date, very close amount


class AppleMatchScorer:
    """Apple-specific match scoring system"""
    
    @staticmethod
    def calculate_confidence(ynab_amount: float,
                           apple_amount: float, 
                           ynab_date: datetime,
                           apple_date: datetime,
                           match_type: AppleMatchType,
                           **kwargs) -> float:
        """
        Calculate match confidence score (0.0 to 1.0) for Apple receipts.
        
        Args:
            ynab_amount: YNAB transaction amount in dollars (positive)
            apple_amount: Apple receipt total in dollars
            ynab_date: YNAB transaction date
            apple_date: Apple receipt date
            match_type: Type of match being scored
            **kwargs: Additional parameters for specific match types
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence
        confidence = 1.0
        
        # Amount accuracy scoring
        amount_diff = abs(ynab_amount - apple_amount)
        confidence *= AppleMatchScorer._score_amount_accuracy(amount_diff, ynab_amount, match_type)
        
        # Date accuracy scoring
        date_diff_days = abs((ynab_date.date() - apple_date.date()).days)
        confidence *= AppleMatchScorer._score_date_accuracy(date_diff_days, match_type)
        
        # Match type bonus/penalty
        confidence *= AppleMatchScorer._get_match_type_multiplier(match_type)
        
        # Apply minimum thresholds
        confidence = max(0.0, min(1.0, confidence))
        
        return round(confidence, 3)
    
    @staticmethod
    def _score_amount_accuracy(amount_diff: float, ynab_amount: float, match_type: AppleMatchType) -> float:
        """
        Score the accuracy of amount matching.
        
        Args:
            amount_diff: Absolute difference in dollars
            ynab_amount: YNAB transaction amount for percentage calculation
            match_type: Type of match for context
            
        Returns:
            Score multiplier (0.0 to 1.0)
        """
        if amount_diff == 0:
            return 1.0  # Perfect amount match
            
        # Very small differences (likely rounding)
        if amount_diff <= 0.01:
            return 0.98
            
        # Small differences (minor discrepancies)
        if amount_diff <= 0.05:
            return 0.90
            
        # Moderate differences
        if amount_diff <= 0.25:
            return 0.75
            
        # Percentage-based penalty for larger differences
        if ynab_amount > 0:
            percentage_diff = amount_diff / ynab_amount
            if percentage_diff <= 0.02:  # Within 2%
                return 0.80
            elif percentage_diff <= 0.05:  # Within 5%
                return 0.60
            elif percentage_diff <= 0.10:  # Within 10%
                return 0.40
            else:
                return 0.10  # Large discrepancy
        
        return 0.10  # Default for edge cases
    
    @staticmethod
    def _score_date_accuracy(date_diff_days: int, match_type: AppleMatchType) -> float:
        """
        Score the accuracy of date matching.
        
        Args:
            date_diff_days: Absolute difference in days
            match_type: Type of match for context
            
        Returns:
            Score multiplier (0.0 to 1.0)
        """
        if date_diff_days == 0:
            return 1.0  # Same day - perfect
            
        if date_diff_days == 1:
            return 0.90  # 1 day off - very good
            
        if date_diff_days == 2:
            return 0.75  # 2 days off - acceptable
            
        if date_diff_days <= 5:
            return 0.50  # Up to 5 days - possible but lower confidence
            
        if date_diff_days <= 10:
            return 0.25  # Up to 10 days - unlikely but possible
            
        return 0.10  # More than 10 days - very unlikely
    
    @staticmethod
    def _get_match_type_multiplier(match_type: AppleMatchType) -> float:
        """
        Get confidence multiplier based on match type.
        
        Args:
            match_type: Type of match
            
        Returns:
            Multiplier for confidence score
        """
        multipliers = {
            AppleMatchType.EXACT_MATCH: 1.0,        # Perfect scenario
            AppleMatchType.DATE_WINDOW: 0.95,       # Slight penalty for date window
            AppleMatchType.AMOUNT_TOLERANCE: 0.90   # Penalty for amount tolerance
        }
        
        return multipliers.get(match_type, 0.80)  # Default for unknown types


def create_match_result(ynab_transaction: Dict[str, Any],
                       apple_receipt: Optional[Dict[str, Any]],
                       confidence: float,
                       match_type: Optional[AppleMatchType],
                       **kwargs) -> Dict[str, Any]:
    """
    Create a standardized match result dictionary.
    
    Args:
        ynab_transaction: YNAB transaction data
        apple_receipt: Apple receipt data (None if no match)
        confidence: Match confidence score
        match_type: Type of match made
        **kwargs: Additional metadata
        
    Returns:
        Standardized match result dictionary
    """
    result = {
        "ynab_transaction": {
            "id": ynab_transaction.get("transaction_id", ""),
            "date": ynab_transaction.get("date_str", ""),
            "amount": ynab_transaction.get("amount_dollars", 0.0),
            "payee_name": ynab_transaction.get("payee_name", ""),
            "account_name": ynab_transaction.get("account_name", "")
        },
        "matched": apple_receipt is not None,
        "match_confidence": confidence,
        "match_strategy": match_type.value if match_type else None,
        "apple_receipts": [apple_receipt] if apple_receipt else [],
        "unmatched_amount": 0.0 if apple_receipt else ynab_transaction.get("amount_dollars", 0.0),
        "match_details": {
            "date_diff_days": kwargs.get("date_diff_days", 0),
            "amount_diff": kwargs.get("amount_diff", 0.0),
            "apple_id": apple_receipt.get("apple_id", "") if apple_receipt else "",
            "order_id": apple_receipt.get("order_id", "") if apple_receipt else ""
        }
    }
    
    return result


def score_batch_results(results: list) -> Dict[str, Any]:
    """
    Calculate summary statistics for a batch of match results.
    
    Args:
        results: List of match result dictionaries
        
    Returns:
        Summary statistics dictionary
    """
    if not results:
        return {"total_transactions": 0}
    
    total_transactions = len(results)
    matched_results = [r for r in results if r["matched"]]
    matched_count = len(matched_results)
    
    # Calculate amounts
    total_amount = sum(r.get("ynab_transaction", {}).get("amount", 0) for r in results)
    matched_amount = sum(r.get("ynab_transaction", {}).get("amount", 0) for r in matched_results)
    unmatched_amount = total_amount - matched_amount
    
    # Confidence statistics
    if matched_results:
        confidences = [r["match_confidence"] for r in matched_results]
        avg_confidence = sum(confidences) / len(confidences)
        min_confidence = min(confidences)
        max_confidence = max(confidences)
    else:
        avg_confidence = min_confidence = max_confidence = 0.0
    
    # Strategy breakdown
    strategy_counts = {}
    for result in matched_results:
        strategy = result.get("match_strategy", "unknown")
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    
    # Confidence distribution
    confidence_ranges = {
        "perfect": len([r for r in matched_results if r["match_confidence"] >= 0.95]),
        "high": len([r for r in matched_results if 0.80 <= r["match_confidence"] < 0.95]),
        "medium": len([r for r in matched_results if 0.60 <= r["match_confidence"] < 0.80]),
        "low": len([r for r in matched_results if r["match_confidence"] < 0.60])
    }
    
    summary = {
        "total_transactions": total_transactions,
        "matched": matched_count,
        "unmatched": total_transactions - matched_count,
        "match_rate": matched_count / total_transactions if total_transactions > 0 else 0.0,
        "confidence_stats": {
            "average": round(avg_confidence, 3),
            "minimum": round(min_confidence, 3),
            "maximum": round(max_confidence, 3)
        },
        "confidence_distribution": confidence_ranges,
        "amount_stats": {
            "total_amount": round(total_amount, 2),
            "matched_amount": round(matched_amount, 2),
            "unmatched_amount": round(unmatched_amount, 2)
        },
        "strategy_breakdown": strategy_counts
    }
    
    return summary


if __name__ == "__main__":
    # Test the scorer
    from datetime import datetime
    
    # Test data
    ynab_date = datetime(2024, 11, 15)
    apple_date = datetime(2024, 11, 15)
    
    # Test exact match
    confidence = AppleMatchScorer.calculate_confidence(
        ynab_amount=19.99,
        apple_amount=19.99,
        ynab_date=ynab_date,
        apple_date=apple_date,
        match_type=AppleMatchType.EXACT_MATCH
    )
    print(f"Exact match confidence: {confidence}")
    
    # Test date window match
    apple_date_delayed = datetime(2024, 11, 16)
    confidence = AppleMatchScorer.calculate_confidence(
        ynab_amount=19.99,
        apple_amount=19.99,
        ynab_date=ynab_date,
        apple_date=apple_date_delayed,
        match_type=AppleMatchType.DATE_WINDOW
    )
    print(f"Date window match confidence: {confidence}")
    
    # Test amount tolerance
    confidence = AppleMatchScorer.calculate_confidence(
        ynab_amount=19.99,
        apple_amount=20.00,
        ynab_date=ynab_date,
        apple_date=apple_date,
        match_type=AppleMatchType.AMOUNT_TOLERANCE
    )
    print(f"Amount tolerance match confidence: {confidence}")
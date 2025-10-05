#!/usr/bin/env python3
"""
Apple Receipt Loader Module

Loads and processes Apple receipts from the export JSON files.
Provides data normalization and filtering functionality.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..core.config import get_config


def find_latest_apple_export(base_path: str | None = None) -> str | None:
    """
    Find the most recent Apple receipt export directory.

    Args:
        base_path: Base path to Apple exports directory (uses config if None)

    Returns:
        Path to the latest export directory, or None if none found
    """
    if base_path is None:
        config = get_config()
        base_path = str(config.apple.data_dir / "exports")

    # Handle both absolute and relative paths
    if not Path(base_path).is_absolute():
        # If relative, try from current working directory first
        export_path = Path(base_path)
        if not export_path.exists():
            # If that doesn't work, try from script's parent directory
            script_parent = Path(__file__).parent.parent.parent
            export_path = script_parent / base_path
    else:
        export_path = Path(base_path)

    if not export_path.exists():
        return None

    # Find all export directories with timestamp pattern
    export_dirs = [
        item
        for item in export_path.iterdir()
        if item.is_dir() and item.name.startswith("20") and "apple_receipts_export" in item.name
    ]

    if not export_dirs:
        return None

    # Sort by directory name (which includes timestamp) and return latest
    latest_dir = sorted(export_dirs, key=lambda x: x.name, reverse=True)[0]
    return str(latest_dir)


def load_apple_receipts(export_path: str | None = None) -> list[dict[str, Any]]:
    """
    Load Apple receipts from the latest export.

    Args:
        export_path: Optional specific export path, otherwise finds latest

    Returns:
        List of receipt dictionaries
    """
    if export_path is None:
        # Find the latest export directory
        latest_export = find_latest_apple_export()
        if latest_export is None:
            raise FileNotFoundError("No Apple receipt exports found")
        export_path = latest_export

    # Load the combined receipts file
    receipts_file = Path(export_path) / "all_receipts_combined.json"
    if not receipts_file.exists():
        raise FileNotFoundError(f"Receipt file not found: {receipts_file}")

    with open(receipts_file) as f:
        receipts_data: list[dict[str, Any]] = json.load(f)

    print(f"Loaded {len(receipts_data)} Apple receipts from {export_path}")
    return receipts_data


def normalize_apple_receipt_data(receipts: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Normalize Apple receipt data into a standardized DataFrame.

    Args:
        receipts: Raw receipt data from JSON

    Returns:
        DataFrame with normalized receipt data
    """
    normalized_data = []

    for receipt in receipts:
        # Extract core receipt information
        try:
            # Parse receipt date to standard format
            receipt_date_str = receipt.get("receipt_date", "")
            receipt_date = parse_apple_date(receipt_date_str)

            # Skip receipts without valid dates
            if receipt_date is None:
                print(
                    f"Warning: Skipping receipt {receipt.get('order_id', 'unknown')} due to invalid date: '{receipt_date_str}'"
                )
                continue

            # Get total amount (already in cents from parsing)
            total = receipt.get("total", 0)
            if total is None:
                total = 0

            # Create normalized record
            normalized_record = {
                "apple_id": receipt.get("apple_id", ""),
                "receipt_date": receipt_date,
                "receipt_date_str": receipt_date_str,
                "order_id": receipt.get("order_id", ""),
                "document_number": receipt.get("document_number", ""),
                "total": total,  # Amount in cents
                "currency": receipt.get("currency", "USD"),
                "subtotal": receipt.get("subtotal"),
                "tax": receipt.get("tax"),
                "items": receipt.get("items", []),
                "format_detected": receipt.get("format_detected", ""),
                "base_name": receipt.get("base_name", ""),
                "item_count": len(receipt.get("items", [])),
            }

            normalized_data.append(normalized_record)

        except Exception as e:
            print(f"Warning: Failed to normalize receipt {receipt.get('order_id', 'unknown')}: {e}")
            continue

    df = pd.DataFrame(normalized_data)

    # Sort by receipt date for easier processing
    if not df.empty:
        df = df.sort_values("receipt_date")

    print(f"Normalized {len(df)} receipts successfully")
    return df


def parse_apple_date(date_str: str) -> datetime | None:
    """
    Parse Apple receipt date string into datetime object.

    Apple uses formats like "Nov 3, 2020" or "Apr 16, 2025"

    Args:
        date_str: Date string from Apple receipt

    Returns:
        Parsed datetime object, or None if parsing fails
    """
    if not date_str:
        return None

    try:
        # Handle Apple's "MMM d, yyyy" format
        parsed_date = datetime.strptime(date_str, "%b %d, %Y")
        return parsed_date
    except ValueError:
        try:
            # Try alternative format if needed
            parsed_date = datetime.strptime(date_str, "%B %d, %Y")
            return parsed_date
        except ValueError:
            print(f"Warning: Could not parse date '{date_str}'")
            return None


def filter_receipts_by_date_range(receipts_df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Filter receipts to a specific date range.

    Args:
        receipts_df: DataFrame of receipts
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)

    Returns:
        Filtered DataFrame
    """
    if receipts_df.empty:
        return receipts_df

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # Filter receipts within date range
    mask = (receipts_df["receipt_date"] >= start_dt) & (receipts_df["receipt_date"] <= end_dt)
    filtered_df = receipts_df[mask].copy()

    print(f"Filtered to {len(filtered_df)} receipts between {start_date} and {end_date}")
    return filtered_df


def get_apple_receipt_summary(receipts_df: pd.DataFrame) -> dict[str, Any]:
    """
    Generate summary statistics for Apple receipts.

    Args:
        receipts_df: DataFrame of receipts

    Returns:
        Dictionary with summary statistics
    """
    if receipts_df.empty:
        return {"total_receipts": 0}

    summary = {
        "total_receipts": len(receipts_df),
        "total_amount": receipts_df["total"].sum(),
        "date_range": {
            "earliest": (
                receipts_df["receipt_date"].min().strftime("%Y-%m-%d")
                if not receipts_df["receipt_date"].isnull().all()
                else None
            ),
            "latest": (
                receipts_df["receipt_date"].max().strftime("%Y-%m-%d")
                if not receipts_df["receipt_date"].isnull().all()
                else None
            ),
        },
        "apple_ids": receipts_df["apple_id"].unique().tolist(),
        "average_amount": receipts_df["total"].mean(),
        "formats_detected": receipts_df["format_detected"].value_counts().to_dict(),
    }

    return summary

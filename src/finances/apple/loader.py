#!/usr/bin/env python3
"""
Apple Receipt Loader Module

Loads and processes Apple receipts from the export JSON files.
Provides data normalization and filtering functionality.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..core.config import get_config
from .parser import ParsedReceipt

logger = logging.getLogger(__name__)


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


def load_apple_receipts(export_path: str | None = None) -> list[ParsedReceipt]:
    """
    Load Apple receipts from individual JSON files as domain models.

    The Apple receipt parsing flow writes individual JSON files (one per receipt),
    so this loader reads all *.json files from the export directory.

    Args:
        export_path: Optional specific export path, otherwise finds latest

    Returns:
        List of ParsedReceipt domain models with typed fields (Money, FinancialDate)
    """
    if export_path is None:
        # Find the latest export directory
        latest_export = find_latest_apple_export()
        if latest_export is None:
            raise FileNotFoundError("No Apple receipt exports found")
        export_path = latest_export

    export_dir = Path(export_path)

    # Load all individual JSON receipt files
    json_files = list(export_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No Apple receipt JSON files found in {export_dir}")

    receipts_data = []
    for json_file in json_files:
        with open(json_file) as f:
            receipt_dict = json.load(f)
            receipts_data.append(receipt_dict)

    # Convert dicts to domain models
    receipts = [ParsedReceipt.from_dict(receipt_dict) for receipt_dict in receipts_data]

    logger.info("Loaded %d Apple receipts from %s", len(receipts), export_dir)
    return receipts


def receipts_to_dataframe(receipts: list[ParsedReceipt]) -> pd.DataFrame:
    """
    Convert ParsedReceipt domain models to DataFrame (temporary adapter).

    This is a temporary adapter for code that still uses DataFrames.
    New code should work directly with ParsedReceipt domain models.

    Args:
        receipts: List of ParsedReceipt domain models

    Returns:
        DataFrame with receipt data
    """
    normalized_data = []

    for receipt in receipts:
        # Convert domain model to dict format for DataFrame
        try:
            # Get receipt date as datetime
            receipt_date = None
            receipt_date_str = ""
            if receipt.receipt_date:
                receipt_date_str = receipt.receipt_date.to_iso_string()
                receipt_date = parse_apple_date(receipt_date_str)

            # Create normalized record
            normalized_record = {
                "apple_id": receipt.apple_id or "",
                "receipt_date": receipt_date,
                "receipt_date_str": receipt_date_str,
                "order_id": receipt.order_id or "",
                "document_number": receipt.document_number or "",
                "total": receipt.total.to_cents() if receipt.total else 0,
                "currency": receipt.currency,
                "subtotal": receipt.subtotal.to_cents() if receipt.subtotal else None,
                "tax": receipt.tax.to_cents() if receipt.tax else None,
                "items": [
                    {
                        "title": item.title,
                        "cost": item.cost.to_cents(),
                        "quantity": item.quantity,
                        "subscription": item.subscription,
                    }
                    for item in receipt.items
                ],
                "format_detected": receipt.format_detected or "",
                "base_name": receipt.base_name or "",
                "item_count": len(receipt.items),
            }

            normalized_data.append(normalized_record)

        except (AttributeError, ValueError, TypeError) as e:
            logger.warning("Failed to convert receipt %s: %s", receipt.order_id or "unknown", e)
            continue

    df = pd.DataFrame(normalized_data)

    # Sort by receipt date for easier processing
    if not df.empty and "receipt_date" in df.columns:
        df = df.sort_values("receipt_date")

    logger.info("Converted %d receipts to DataFrame", len(df))
    return df


def parse_apple_date(date_str: str) -> datetime | None:
    """
    Parse Apple receipt date string into datetime object.

    Apple uses formats like "Nov 3, 2020" or "Apr 16, 2025"
    Parser may normalize dates to ISO format "YYYY-MM-DD"

    Args:
        date_str: Date string from Apple receipt

    Returns:
        Parsed datetime object, or None if parsing fails
    """
    if not date_str:
        return None

    # Try ISO format first (from parser normalization)
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed_date
    except ValueError:
        pass

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
            logger.warning("Could not parse date '%s'", date_str)
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

    logger.info("Filtered to %d receipts between %s and %s", len(filtered_df), start_date, end_date)
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

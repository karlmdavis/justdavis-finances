#!/usr/bin/env python3
"""
JSON Utilities Module

Provides centralized JSON reading and writing functions with consistent formatting.
All JSON files in the codebase should use these utilities to ensure pretty-printing
and consistent formatting for better debugging and searchability.
"""

import json
from pathlib import Path
from typing import Any


def write_json(filepath: str | Path, data: Any, ensure_ascii: bool = False, sort_keys: bool = False) -> None:
    """
    Write data to a JSON file with standard pretty-printing.

    Args:
        filepath: Path to the JSON file
        data: Data to write to the file
        ensure_ascii: If True, escape non-ASCII characters (default: False)
        sort_keys: If True, sort dictionary keys (default: False)
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=ensure_ascii, sort_keys=sort_keys)


def read_json(filepath: str | Path) -> Any:
    """
    Read data from a JSON file.

    Args:
        filepath: Path to the JSON file

    Returns:
        The parsed JSON data
    """
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def format_json(data: Any, ensure_ascii: bool = False, sort_keys: bool = False, default: Any = None) -> str:
    """
    Format data as a pretty-printed JSON string.

    Args:
        data: Data to format
        ensure_ascii: If True, escape non-ASCII characters (default: False)
        sort_keys: If True, sort dictionary keys (default: False)
        default: Function to serialize non-JSON types (default: None)

    Returns:
        Pretty-printed JSON string
    """
    if default is not None:
        return json.dumps(data, indent=2, ensure_ascii=ensure_ascii, sort_keys=sort_keys, default=default)
    return json.dumps(data, indent=2, ensure_ascii=ensure_ascii, sort_keys=sort_keys)


def write_json_with_defaults(filepath: str | Path, data: Any, default: Any = str) -> None:
    """
    Write data to a JSON file with a custom default serializer for non-JSON types.

    Args:
        filepath: Path to the JSON file
        data: Data to write to the file
        default: Function to serialize non-JSON types (default: str)
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=default)

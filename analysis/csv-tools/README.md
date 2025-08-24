# CSV Tools

Generic CSV analysis utilities for working with financial data using [nushell](https://www.nushell.sh/).

## Overview

This directory contains tools for safely analyzing CSV files with powerful nushell pipelines. The primary tool, `open.nu`, provides a secure wrapper around nushell's CSV processing capabilities.

## Tools

### `open.nu` - Generic CSV Opener with Pipeline Support

A nushell wrapper script that opens CSV files and optionally applies data processing pipelines.

**Usage:**
```bash
./open.nu <file_path> [pipeline_commands...]
```

## Examples

All examples below have been tested and verified to work.

### Basic File Inspection

**View first few rows:**
```bash
analysis/csv-tools/open.nu "amazon/data/2025-08-24_karl_amazon_data/Retail.OrderHistory.1/Retail.OrderHistory.1.csv" "first 3"
```

**Select specific columns:**
```bash
analysis/csv-tools/open.nu "amazon/data/2025-08-24_karl_amazon_data/Retail.OrderHistory.1/Retail.OrderHistory.1.csv" "first 3 | select 'Order ID' 'Product Name' 'Total Owed'"
```

### Filtering Data

**Search for products containing "Guitar":**
```bash
analysis/csv-tools/open.nu "amazon/data/2025-08-24_karl_amazon_data/Retail.OrderHistory.1/Retail.OrderHistory.1.csv" "where 'Product Name' =~ 'Guitar' | select 'Product Name' 'Total Owed'"
```

**Filter by specific values:**
```bash
analysis/csv-tools/open.nu "amazon/data/2025-08-24_karl_amazon_data/Retail.OrderHistory.1/Retail.OrderHistory.1.csv" "where Currency == 'USD' | first 5"
```

### Sorting and Analysis

**Sort by amount (descending, lexicographic):**
```bash
analysis/csv-tools/open.nu "amazon/data/2025-08-24_karl_amazon_data/Retail.OrderHistory.1/Retail.OrderHistory.1.csv" "sort-by 'Total Owed' --reverse | first 3 | select 'Product Name' 'Total Owed'"
```

**Count records:**
```bash
analysis/csv-tools/open.nu "amazon/data/2025-08-24_karl_amazon_data/Retail.OrderHistory.1/Retail.OrderHistory.1.csv" "length"
```

## When to Use This Tool

### ✅ **Good Use Cases:**
- **Quick CSV inspection** - View structure and sample data
- **Simple filtering** - Find rows matching criteria 
- **Column selection** - Extract specific fields
- **Basic sorting** - Order data by columns
- **Safe exploration** - Prevent accidental file modifications

### ⚠️  **Limitations:**
- **String-based operations** - Numeric comparisons require type conversion
- **Simple aggregations only** - Complex grouping may require direct nushell
- **File path handling** - Must provide full relative/absolute paths

### 🚫 **Not Recommended For:**
- **Complex data transformations** - Use pandas/Python for heavy processing
- **Large file processing** - Memory constraints may apply
- **Production data pipelines** - This is an exploration tool

## Alternative Approaches

For more complex analysis, consider:

- **Python + pandas**: `uv run python3 -c "import pandas as pd; df = pd.read_csv('file.csv'); print(df.head())"`
- **Direct nushell**: `nu -c "open file.csv | where amount > 100"`
- **jq for JSON**: `jq '.[] | select(.amount > 100)' file.json`

## Security Notes

- This tool is **read-only** - it cannot modify your CSV files
- File paths are passed directly to nushell - ensure paths are trusted
- Pipeline commands are executed in nushell context - validate syntax

## Technical Details

- **Shell**: Uses `/opt/homebrew/bin/nu` (Homebrew nushell installation)
- **File handling**: Leverages nushell's built-in CSV parser
- **Error handling**: Basic error propagation from nushell
- **Memory**: Loads entire CSV into memory (suitable for typical financial datasets)
#!/bin/bash

# Amazon Data Extraction Helper Script
# Usage: ./extract_amazon_data.sh "Your Orders.zip" accountname
# Example: ./extract_amazon_data.sh "Your Orders Karl.zip" karl

set -e  # Exit on error

# Check arguments
if [ $# -ne 2 ]; then
    echo "Usage: $0 <zip_file> <account_name>"
    echo "Example: $0 \"Your Orders.zip\" karl"
    exit 1
fi

ZIP_FILE="$1"
ACCOUNT_NAME="$2"
DATE_STAMP=$(date +%Y-%m-%d)
DATA_DIR="amazon/data"
TARGET_DIR="${DATA_DIR}/${DATE_STAMP}_${ACCOUNT_NAME}_amazon_data"

# Validate zip file exists
if [ ! -f "$ZIP_FILE" ]; then
    echo "Error: ZIP file '$ZIP_FILE' not found"
    exit 1
fi

# Create data directory if it doesn't exist
if [ ! -d "$DATA_DIR" ]; then
    echo "Creating data directory: $DATA_DIR"
    mkdir -p "$DATA_DIR"
fi

# Check if target directory already exists
if [ -d "$TARGET_DIR" ]; then
    echo "Warning: Directory '$TARGET_DIR' already exists"
    read -p "Do you want to overwrite it? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Extraction cancelled"
        exit 1
    fi
    echo "Removing existing directory..."
    rm -rf "$TARGET_DIR"
fi

# Create target directory
echo "Creating directory: $TARGET_DIR"
mkdir -p "$TARGET_DIR"

# Extract ZIP file
echo "Extracting '$ZIP_FILE' to '$TARGET_DIR'..."
unzip -q "$ZIP_FILE" -d "$TARGET_DIR"

# Verify extraction
if [ -d "$TARGET_DIR/Retail.OrderHistory.1" ]; then
    echo "✓ Successfully extracted retail order history"
else
    echo "⚠ Warning: Retail order history not found"
fi

if [ -d "$TARGET_DIR/Digital-Ordering.1" ]; then
    echo "✓ Successfully extracted digital order history"
else
    echo "⚠ Warning: Digital order history not found"
fi

# Count files
TOTAL_FILES=$(find "$TARGET_DIR" -type f | wc -l | tr -d ' ')
echo ""
echo "Extraction complete!"
echo "  Account: $ACCOUNT_NAME"
echo "  Directory: $TARGET_DIR"
echo "  Total files: $TOTAL_FILES"
echo ""
echo "The Amazon transaction matching tools will automatically discover this data."

# Optional: Remove ZIP file
read -p "Do you want to delete the original ZIP file? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm "$ZIP_FILE"
    echo "✓ ZIP file deleted"
fi

echo ""
echo "Next steps:"
echo "1. Run single transaction matching:"
echo "   uv run python analysis/amazon_transaction_matching/match_single_transaction.py --help"
echo ""
echo "2. Run batch processing:"
echo "   uv run python analysis/amazon_transaction_matching/match_transactions_batch.py --start YYYY-MM-DD --end YYYY-MM-DD"
echo ""
echo "3. To search only this account, add: --accounts $ACCOUNT_NAME"
#!/usr/bin/env python3
"""
Test problematic receipt parsing to understand issues better.
"""

from receipt_parser import AppleReceiptParser, get_extracted_content_dir

def test_receipt(base_name, content_dir):
    """Test a single receipt and show detailed results."""
    print(f"\n{'='*80}")
    print(f"TESTING: {base_name}")
    print('='*80)
    
    # Show plain text content first
    txt_path = content_dir / f"{base_name}.txt"
    if txt_path.exists():
        print("PLAIN TEXT CONTENT:")
        print("-" * 40)
        with open(txt_path, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines[:40], 1):  # First 40 lines
            print(f"{i:2}: {line.rstrip()}")
        
        if len(lines) > 40:
            print(f"... and {len(lines) - 40} more lines")
    
    # Parse with current parser
    parser = AppleReceiptParser()
    receipt = parser.parse_receipt(base_name, content_dir)
    
    print(f"\nPARSED RESULTS:")
    print("-" * 40)
    print(f"Format: {receipt.format_detected}")
    print(f"Apple ID: {receipt.apple_id}")
    print(f"Order ID: {receipt.order_id}")
    print(f"Document Number: {receipt.document_number}")
    print(f"Subtotal: ${receipt.subtotal:.2f}" if receipt.subtotal else "Subtotal: None")
    print(f"Tax: ${receipt.tax:.2f}" if receipt.tax else "Tax: None")
    print(f"Total: ${receipt.total:.2f}" if receipt.total else "Total: None")
    print(f"Items: {len(receipt.items)}")
    
    for i, item in enumerate(receipt.items, 1):
        cost_str = f"${item['cost']:.2f}" if item.get('cost') else "No price"
        print(f"  Item {i}: [{item.get('type', 'unknown')}] {item['title']} - {cost_str}")

def main():
    """Test problematic receipts."""
    parser = AppleReceiptParser()
    content_dir = get_extracted_content_dir()
    
    # Test receipts that are missing items
    problematic_receipts = [
        '20211020_094758_Your receipt from Apple__82836ca5',  # iCloud+ with template variables
        '20211104_222513_Your receipt from Apple__97785e05',  # Apple TV+ with subtotal/tax
        '20211123_110709_Your receipt from Apple__f84d4651',  # Another missing items case
    ]
    
    for base_name in problematic_receipts:
        test_receipt(base_name, content_dir)

if __name__ == "__main__":
    main()
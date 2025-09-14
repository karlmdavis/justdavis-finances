#!/usr/bin/env python3
"""
Test a single receipt parsing to debug issues.
"""

from receipt_parser import AppleReceiptParser, get_extracted_content_dir

def main():
    parser = AppleReceiptParser()
    content_dir = get_extracted_content_dir()
    
    # Test problematic receipts
    test_cases = [
        '20240916_034902_Your receipt from Apple__b7a09dca',  # Legacy HTML missing financial
        '20201221_062221_Your receipt from Apple__22c5a901',  # Plain text missing items
    ]
    
    for base_name in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {base_name}")
        print('='*60)
        
        receipt = parser.parse_receipt(base_name, content_dir)
        
        print(f"Format: {receipt.format_detected}")
        print(f"Apple ID: {receipt.apple_id}")
        print(f"Order ID: {receipt.order_id}")
        print(f"Document Number: {receipt.document_number}")
        print(f"Subtotal: ${receipt.subtotal:.2f}" if receipt.subtotal else "Subtotal: None")
        print(f"Tax: ${receipt.tax:.2f}" if receipt.tax else "Tax: None") 
        print(f"Total: ${receipt.total:.2f}" if receipt.total else "Total: None")
        print(f"Items: {len(receipt.items)}")
        
        for i, item in enumerate(receipt.items):
            print(f"  Item {i+1}: {item['title']} - ${item['cost']:.2f}" if item['cost'] else f"  Item {i+1}: {item['title']} - No price")
            
        print(f"Parsing metadata: {receipt.parsing_metadata}")

if __name__ == "__main__":
    main()
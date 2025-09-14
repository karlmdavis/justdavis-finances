#!/usr/bin/env python3
"""Debug parser for specific receipt."""

import re
from pathlib import Path
from bs4 import BeautifulSoup

def debug_receipt(filename):
    """Debug parsing of specific receipt."""
    
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    
    email_dirs = [d for d in data_dir.glob("*_apple_emails") if d.is_dir()]
    latest_dir = max(email_dirs, key=lambda d: d.name)
    content_dir = latest_dir / "extracted_content"
    
    html_path = content_dir / filename
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    soup = BeautifulSoup(content, 'lxml')
    
    print(f"Debugging: {filename}")
    print("="*50)
    
    # Focus on desktop version
    desktop_div = soup.select_one('div.aapl-desktop-div')
    search_root = desktop_div if desktop_div else soup
    
    print(f"Desktop div found: {desktop_div is not None}")
    
    # Debug Apple ID extraction - search for exact match
    print("\n--- APPLE ID DEBUGGING ---")
    
    # Look for the specific patterns we saw
    apple_account_spans = soup.find_all('span', string=re.compile(r'^APPLE ACCOUNT$', re.I))
    print(f"Found {len(apple_account_spans)} exact 'APPLE ACCOUNT' spans")
    
    for span in apple_account_spans:
        print(f"\nFound span: {span}")
        td_container = span.parent
        print(f"Parent container: {td_container.name}")
        td_text = td_container.get_text()
        print(f"TD text: {repr(td_text)}")
        
        email_match = re.search(r'([\w\.-]+@[\w\.-]+\.\w+)', td_text)
        if email_match:
            print(f"✓ Found email: {email_match.group(1)}")
    
    # Also try direct text search
    print("\n--- DIRECT EMAIL SEARCH ---")
    all_text = soup.get_text()
    email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', all_text)
    print(f"Found emails in entire document: {email_matches}")
    
    # Debug date extraction
    print("\n--- DATE DEBUGGING ---")
    
    # Search for DATE in spans
    date_spans = soup.find_all('span', string=re.compile(r'DATE', re.I))
    print(f"Found {len(date_spans)} spans with DATE")
    
    for span in date_spans:
        print(f"Date span: {span}")
        td_container = span.parent
        print(f"Parent: {td_container.name}")
        print(f"TD text: {repr(td_container.get_text())}")
        
        # Look for span with dir="auto"
        date_span = td_container.find('span', {'dir': 'auto'})
        if date_span:
            print(f"✓ Found date: {date_span.get_text().strip()}")
    
    # Also search for dates in the entire text
    date_pattern = r'[A-Z][a-z]{2} \d{1,2}, \d{4}'  # "Sep 20, 2024"
    all_text = soup.get_text()
    date_matches = re.findall(date_pattern, all_text)
    print(f"Found date patterns in text: {date_matches}")
    if date_label:
        print("✓ Found DATE label")
        date_container = date_label.parent.parent if hasattr(date_label.parent, 'parent') else date_label.parent
        print(f"Date container: {date_container.name}")
        
        # Try span with dir="auto"
        date_span = date_container.find('span', {'dir': 'auto'})
        if date_span:
            print(f"✓ Found date span: {date_span.get_text().strip()}")
        else:
            print("✗ No date span with dir='auto'")
            
            # Try all spans
            spans = date_container.find_all('span')
            print(f"Found {len(spans)} spans in date container:")
            for span in spans:
                print(f"  Span: {span.get_text().strip()}")
    else:
        print("✗ No DATE label found")
    
    # Debug financial data
    print("\n--- FINANCIAL DATA DEBUGGING ---")
    
    # Search for all spans with Subtotal
    subtotal_spans = soup.find_all('span', string=re.compile(r'Subtotal', re.I))
    print(f"Found {len(subtotal_spans)} spans with Subtotal")
    
    for span in subtotal_spans:
        print(f"\nSubtotal span: {span}")
        # Find parent table row
        table_row = span.parent
        while table_row and table_row.name != 'tr':
            table_row = table_row.parent
        
        if table_row:
            print(f"Found table row: {table_row.name}")
            tds = table_row.find_all('td')
            print(f"Row has {len(tds)} columns")
            for i, td in enumerate(tds):
                print(f"  Column {i+1}: {td.get_text().strip()}")
                spans = td.find_all('span')
                for span in spans:
                    span_text = span.get_text().strip()
                    if span_text.startswith('$'):
                        print(f"    ✓ Found amount: {span_text}")
        else:
            print("✗ No table row found for this span")
    
    # Also search for dollar amounts directly
    print(f"\n--- DIRECT FINANCIAL SEARCH ---")
    dollar_amounts = re.findall(r'\$[0-9,.]+', soup.get_text())
    print(f"Found dollar amounts: {dollar_amounts}")

if __name__ == "__main__":
    debug_receipt("20240921_102756_Your receipt from Apple__7f808f32-formatted-simple.html")
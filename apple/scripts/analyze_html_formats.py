#!/usr/bin/env python3
"""
Comprehensive HTML Format Analysis for Apple Receipt Parser

This script analyzes all HTML receipt files to identify format patterns,
CSS classes, and structural differences across different time periods.
Used to design the complete HTML-only parsing system.
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib

def get_content_directory():
    """Get the extracted content directory."""
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    
    # Find the most recent email data directory
    email_dirs = [d for d in data_dir.glob("*_apple_emails") if d.is_dir()]
    if not email_dirs:
        raise FileNotFoundError("No Apple email data directories found")
    
    latest_dir = max(email_dirs, key=lambda d: d.name)
    return latest_dir / "extracted_content"

def extract_receipt_date(filename):
    """Extract date from receipt filename."""
    # Format: YYYYMMDD_HHMMSS_Your receipt from Apple__hash.ext
    match = re.match(r'(\d{8})_\d{6}_Your receipt from Apple__', filename)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            pass
    return None

def analyze_css_classes(soup):
    """Analyze CSS classes in the HTML."""
    classes = set()
    for element in soup.find_all(class_=True):
        if isinstance(element.get('class'), list):
            classes.update(element.get('class'))
        else:
            classes.add(element.get('class'))
    return classes

def analyze_html_structure(soup):
    """Analyze the overall HTML structure."""
    structure = {}
    
    # Count different elements
    structure['table_count'] = len(soup.find_all('table'))
    structure['div_count'] = len(soup.find_all('div'))
    structure['span_count'] = len(soup.find_all('span'))
    structure['p_count'] = len(soup.find_all('p'))
    
    # Check for key structural elements
    structure['has_aapl_desktop'] = bool(soup.select('.aapl-desktop-div, .aapl-desktop-tbl'))
    structure['has_aapl_mobile'] = bool(soup.select('.aapl-mobile-div, .aapl-mobile-tbl, .aapl-mobile-cell'))
    structure['has_custom_classes'] = bool(soup.select('[class*="custom-"]'))
    
    # Check for key financial indicators
    structure['has_subtotal'] = bool(soup.find(string=re.compile(r'Subtotal', re.I)))
    structure['has_tax'] = bool(soup.find(string=re.compile(r'Tax', re.I)))
    structure['has_total'] = bool(soup.find(string=re.compile(r'TOTAL', re.I)))
    
    # Check for key metadata indicators
    structure['has_order_id'] = bool(soup.find(string=re.compile(r'ORDER ID', re.I)))
    structure['has_document_no'] = bool(soup.find(string=re.compile(r'DOCUMENT NO', re.I)))
    structure['has_apple_id'] = bool(soup.find(string=re.compile(r'APPLE ID|APPLE ACCOUNT', re.I)))
    
    return structure

def categorize_format(classes, structure, date):
    """Categorize the HTML format based on analysis."""
    year = date.year if date else 0
    
    # Modern HTML (2025+ with custom-* classes)
    if structure['has_custom_classes']:
        return 'modern_html'
    
    # Legacy HTML (2024+ with aapl-* classes)
    elif structure['has_aapl_desktop'] or structure['has_aapl_mobile']:
        return 'legacy_html'
    
    # Early HTML (2020-2023 with different structure)
    elif year <= 2023 and structure['table_count'] > 0:
        return 'early_html'
    
    # Intermediate HTML (transitional formats)
    elif year == 2024 and not (structure['has_aapl_desktop'] or structure['has_custom_classes']):
        return 'intermediate_html'
    
    else:
        return 'unknown_html'

def create_format_fingerprint(classes, structure):
    """Create a unique fingerprint for this format."""
    # Sort classes and create a deterministic representation
    class_list = sorted(list(classes))
    structure_items = sorted(structure.items())
    
    fingerprint_data = {
        'classes': class_list,
        'structure': structure_items
    }
    
    fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.md5(fingerprint_str.encode()).hexdigest()[:12]

def analyze_all_html_formats():
    """Analyze all HTML receipt formats."""
    content_dir = get_content_directory()
    
    # Find all HTML receipt files
    html_files = list(content_dir.glob("*Your receipt from Apple*-formatted-simple.html"))
    
    print(f"Analyzing {len(html_files)} HTML receipt files...")
    
    results = {
        'total_files': len(html_files),
        'analysis_timestamp': datetime.now().isoformat(),
        'format_categories': defaultdict(list),
        'format_fingerprints': {},
        'css_class_analysis': Counter(),
        'temporal_analysis': defaultdict(list),
        'structure_patterns': defaultdict(int),
        'parsing_challenges': []
    }
    
    fingerprint_to_files = defaultdict(list)
    
    for i, html_file in enumerate(html_files):
        if i % 50 == 0:
            print(f"Processed {i} files...")
        
        try:
            # Extract metadata
            receipt_date = extract_receipt_date(html_file.name)
            base_name = html_file.name.replace('-formatted-simple.html', '')
            
            # Parse HTML
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'lxml')
            
            # Analyze structure
            classes = analyze_css_classes(soup)
            structure = analyze_html_structure(soup)
            category = categorize_format(classes, structure, receipt_date)
            fingerprint = create_format_fingerprint(classes, structure)
            
            # Store results
            file_info = {
                'filename': html_file.name,
                'base_name': base_name,
                'date': receipt_date.isoformat() if receipt_date else None,
                'year': receipt_date.year if receipt_date else None,
                'category': category,
                'fingerprint': fingerprint,
                'classes': sorted(list(classes)),
                'structure': structure
            }
            
            results['format_categories'][category].append(file_info)
            fingerprint_to_files[fingerprint].append(file_info)
            
            # Update counters
            results['css_class_analysis'].update(classes)
            if receipt_date:
                results['temporal_analysis'][receipt_date.year].append(category)
            
            # Track structure patterns
            pattern_key = f"tables:{structure['table_count']}_divs:{structure['div_count']}_custom:{structure['has_custom_classes']}_aapl:{structure['has_aapl_desktop']}"
            results['structure_patterns'][pattern_key] += 1
            
        except Exception as e:
            results['parsing_challenges'].append({
                'filename': html_file.name,
                'error': str(e)
            })
    
    # Create fingerprint summary
    for fingerprint, files in fingerprint_to_files.items():
        if len(files) > 1:  # Only store fingerprints shared by multiple files
            results['format_fingerprints'][fingerprint] = {
                'count': len(files),
                'category': files[0]['category'],
                'representative_file': files[0]['filename'],
                'date_range': {
                    'earliest': min(f['date'] for f in files if f['date']),
                    'latest': max(f['date'] for f in files if f['date'])
                },
                'structure': files[0]['structure'],
                'classes': files[0]['classes']
            }
    
    # Generate summary statistics
    results['summary'] = {
        'format_breakdown': {cat: len(files) for cat, files in results['format_categories'].items()},
        'most_common_classes': results['css_class_analysis'].most_common(20),
        'temporal_distribution': {
            year: Counter(categories).most_common() 
            for year, categories in results['temporal_analysis'].items()
        },
        'unique_fingerprints': len(results['format_fingerprints']),
        'parsing_success_rate': (len(html_files) - len(results['parsing_challenges'])) / len(html_files) * 100
    }
    
    return results

def save_analysis_results(results):
    """Save analysis results to file."""
    script_dir = Path(__file__).parent
    output_file = script_dir / "html_format_analysis.json"
    
    # Convert Counter objects to regular dicts for JSON serialization
    results['css_class_analysis'] = dict(results['css_class_analysis'])
    results['structure_patterns'] = dict(results['structure_patterns'])
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"Analysis results saved to: {output_file}")
    return output_file

def print_analysis_summary(results):
    """Print a summary of the analysis results."""
    print("\n" + "="*60)
    print("HTML FORMAT ANALYSIS SUMMARY")
    print("="*60)
    
    print(f"\nTotal HTML files analyzed: {results['total_files']}")
    print(f"Parsing success rate: {results['summary']['parsing_success_rate']:.1f}%")
    print(f"Unique format fingerprints: {results['summary']['unique_fingerprints']}")
    
    print(f"\nFormat Category Breakdown:")
    for category, count in results['summary']['format_breakdown'].items():
        percentage = count / results['total_files'] * 100
        print(f"  {category}: {count} files ({percentage:.1f}%)")
    
    print(f"\nTemporal Distribution:")
    for year in sorted(results['summary']['temporal_distribution'].keys()):
        categories = results['summary']['temporal_distribution'][year]
        print(f"  {year}: {dict(categories)}")
    
    print(f"\nMost Common CSS Classes:")
    for cls, count in results['summary']['most_common_classes'][:10]:
        print(f"  {cls}: {count} occurrences")
    
    if results['parsing_challenges']:
        print(f"\nParsing Challenges ({len(results['parsing_challenges'])}):")
        for challenge in results['parsing_challenges'][:5]:
            print(f"  {challenge['filename']}: {challenge['error']}")

if __name__ == "__main__":
    try:
        print("Starting comprehensive HTML format analysis...")
        results = analyze_all_html_formats()
        
        output_file = save_analysis_results(results)
        print_analysis_summary(results)
        
        print(f"\nAnalysis complete! Results saved to: {output_file}")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
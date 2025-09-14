# Apple Receipt Format Analysis - Corrected Based on Metadata

Analysis Date: 2025-09-13 20:32:37
Revised: 2025-09-14 (Corrected after metadata extraction)
**PREVIOUS ANALYSIS WAS FUNDAMENTALLY FLAWED - THIS IS THE CORRECTED VERSION**

## Summary

- **Total emails processed**: 388 Apple emails
- **Actual purchase receipts**: 327 emails (84%)
- **Other notifications**: 61 emails (16%)
  - Subscription renewals: 29
  - Subscription confirmations: 18
  - Download notifications: 3
  - Price increase notices: 3
  - Expiring subscription notices: 4
  - Other: 4

## Corrected Format Categories Based on Parsing Requirements

**Key Finding**: The previous analysis confused structural differences with parsing method differences. There are actually only **THREE** parsing strategies needed, organized by **temporal evolution and content availability**.

### Category 1: Plain Text Parsing (Primary - 67.9% of receipts)
**Time Period**: 2020-2023, some early 2024
**Detection**: `.txt` files exist and contain receipt data
**Coverage**: 222/327 actual purchase receipts
**Parsing Approach**: Simple text pattern matching

**Advantages:**
- Consistent format across all years
- Easy to parse with regex patterns
- Reliable data extraction
- No HTML complexity

### Category 2: Legacy HTML Parsing (Secondary - 26.3% of receipts) 
**Time Period**: Mid-2024 to early 2025
**Detection**: HTML only, contains `aapl-desktop-tbl` or `aapl-mobile-tbl` classes
**Coverage**: 86/327 receipts
**Parsing Approach**: CSS selectors targeting semantic Apple classes

**Key Selectors:**
- `span.title` - Item names
- `span.artist` - Developers/publishers  
- `span.type` - Purchase types
- `span.device` - Device information
- `td.price-cell` - Prices

### Category 3: Modern HTML Parsing (Newest - 5.8% of receipts)
**Time Period**: Early 2025 onwards
**Detection**: HTML only, contains `custom-*` CSS classes, minimal tables
**Coverage**: 19/327 receipts 
**Parsing Approach**: CSS selectors targeting obfuscated custom classes

**Key Selectors:**
- `p.custom-f41j3e` - Field labels ("Order ID:", "Document:", etc.)
- `p.custom-zresjj` - Field values
- `p.custom-gzadzy` - Service/item names  
- `p.custom-137u684` - Prices

## Parsing Strategy Examples

### Category 1: Plain Text Parsing (Primary Method)
**Example:** Any `.txt` file from 2020-2023 period

**Detection:**
```python
def is_plain_text_available(base_name, content_dir):
    txt_path = content_dir / f"{base_name}.txt"
    return txt_path.exists() and txt_path.stat().st_size > 100
```

**Extraction Strategy:**
```python
# Metadata extraction with regex patterns
ORDER_ID = r'ORDER ID:\s+(\w+)'
DOCUMENT_NO = r'DOCUMENT NO\.:\s+(\d+)'
APPLE_ID = r'([\w\.-]+@[\w\.-]+\.\w+)'
TOTAL = r'TOTAL:\s+\$([0-9,.]+)'
SUBTOTAL = r'Subtotal\s+\$([0-9,.]+)'
TAX = r'Tax\s+\$([0-9,.]+)'

# Item extraction
ITEM_WITH_PRICE = r'^(.+?)\s+\$([0-9,.]+)$'  # End of line price
SECTION_HEADER = r'^(App Store|Books|Music|Movies)$'
```

**Parsing Advantages:**
- Consistent format across 6+ years
- Simple regex-based extraction  
- No HTML parsing complexity
- Reliable metadata and item extraction

### Category 2: Legacy HTML Parsing (Secondary Method)
**Example:** 2024+ receipts with `aapl-desktop-tbl` classes

**Detection:**
```python
def is_legacy_html(soup):
    return (soup.select('table.aapl-desktop-tbl') and 
            not soup.select('[class*="custom-"]'))
```

**Primary Extraction Strategy:**
```python
# Use semantic Apple classes
ORDER_ID = 'span:contains("ORDER ID") + span, span:contains("ORDER ID") + span'
DOCUMENT_NO = 'span:contains("DOCUMENT NO.") + span'
APPLE_ID = 'span:contains("APPLE ID") + text()'

# Item details with semantic classes
ITEM_CELLS = 'td.item-cell'
ITEM_TITLE = 'span.title'
ITEM_ARTIST = 'span.artist' 
ITEM_TYPE = 'span.type'
ITEM_DEVICE = 'span.device'
ITEM_PRICE = 'td.price-cell'

# Financial data
SUBTOTAL = 'td:contains("Subtotal") + td'
TAX = 'td:contains("Tax") + td'
TOTAL = 'td:contains("TOTAL") + td'
```

**Multi-Item Handling:**
```python
# Section-based parsing
sections = soup.select('tr.section-header')
for section in sections:
    section_name = section.get_text().strip()
    # Find items in this section
    item_rows = section.find_next_siblings('tr')
```

**Parsing Advantages:**
- Semantic class names are self-documenting
- Reliable multi-item support
- Clear financial structure
- Fallback compatibility with plain text patterns

### Category 3: Modern HTML Parsing (Newest Method)
**Example:** 2025+ receipts with `custom-*` classes

**Detection:**
```python
def is_modern_html(soup):
    return (soup.select('[class*="custom-"]') and 
            len(soup.select('table')) <= 3)
```

**Primary Extraction Strategy:**
```python
# Use adjacent sibling pattern for metadata
ORDER_ID = 'p:contains("Order ID:") + p'
DOCUMENT_NO = 'p:contains("Document:") + p' 
APPLE_ID = 'p:contains("Apple Account:") + p'

# Item/service details using known custom classes
ITEM_NAME = 'p.custom-gzadzy'  # Service name
ITEM_TYPE = 'p.custom-wogfc8'  # Service type/description
ITEM_PRICE = 'p.custom-137u684'  # Item price

# Financial data in payment section
SUBTOTAL = 'div.payment-information p:contains("Subtotal") + p'
TAX = 'div.payment-information p:contains("Tax") + p' 
PAYMENT_METHOD = 'p.custom-15zbox7'  # "Apple Card"
FINAL_TOTAL = 'p.custom-jhluqm'  # Final amount
```

**Multi-Item Strategy:**
```python
# Modern format uses table rows for multiple items/services
item_rows = soup.select('table.subscription-lockup__container tr.subscription-lockup')
for row in item_rows:
    name = row.select_one('p.custom-gzadzy')
    price = row.select_one('p.custom-137u684')
    # Extract item details
```

**Parsing Challenges:**
- Obfuscated class names may change
- Requires specific class knowledge
- Fewer structural landmarks
- Payment method integrated with total

## Universal Data Extraction Schema

### Consistently Available Fields Across All Categories:
- **Apple Account ID**: Email address (various formats)
- **Purchase Date**: Transaction date  
- **Order ID**: Transaction identifier (90%+ coverage)
- **Document Number**: Receipt document number (80%+ coverage)
- **Item Details**: Names, types, devices, publishers
- **Financial Data**: Subtotals, tax, totals
- **Payment Method**: Available in modern formats

### Parsing Method Comparison:

| Field | Plain Text | Legacy HTML | Modern HTML |
|-------|-----------|-------------|-------------|
| **Coverage** | 222/327 (67.9%) | 86/327 (26.3%) | 19/327 (5.8%) |
| **Time Period** | 2020-2023 | 2024-early 2025 | Mid-2025+ |
| **Reliability** | ★★★★★ | ★★★★☆ | ★★★☆☆ |
| **Implementation** | Simple regex | CSS selectors | CSS + fallbacks |
| **Order ID** | `r'ORDER ID:\s+(\w+)'` | `span:contains("ORDER ID") + span` | `p:contains("Order ID:") + p` |
| **Document No** | `r'DOCUMENT NO\.:\s+(\d+)'` | `span:contains("DOCUMENT NO.") + span` | `p:contains("Document:") + p` |
| **Apple ID** | `r'[\w.-]+@[\w.-]+\.\w+'` | `span:contains("APPLE ID") + text` | `p:contains("Apple Account:") + p` |
| **Item Names** | Text line parsing | `span.title` | `p.custom-gzadzy` |
| **Item Prices** | `r'\$([0-9,.]+)$'` | `td.price-cell` | `p.custom-137u684` |
| **Subtotal** | `r'Subtotal\s+\$([0-9,.]+)'` | `td:contains("Subtotal") + td` | `p:contains("Subtotal") + p` |
| **Total** | `r'TOTAL:\s+\$([0-9,.]+)'` | `td:contains("TOTAL") + td` | `p.custom-jhluqm` |

## Implementation Strategy 

### 1. Format Detection (Corrected)
```python
def detect_receipt_format(base_name, content_dir):
    """Detect format based on content availability and HTML structure."""
    
    # Check plain text availability first
    txt_path = content_dir / f"{base_name}.txt"
    if txt_path.exists() and txt_path.stat().st_size > 100:
        return 'plain_text'
    
    # Fall back to HTML analysis
    html_path = content_dir / f"{base_name}-formatted-simple.html"
    if not html_path.exists():
        return 'unknown'
        
    with open(html_path, 'r') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    
    # Modern CSS format (2025+)
    if soup.select('[class*="custom-"]'):
        return 'modern_html'
    
    # Legacy HTML format (2024+)
    elif soup.select('table.aapl-desktop-tbl, table.aapl-mobile-tbl'):
        return 'legacy_html'
    
    return 'unknown'
```

### 2. Parsing Implementation Priority
```python
class AppleReceiptParser:
    def parse(self, base_name, content_dir):
        format_type = self.detect_receipt_format(base_name, content_dir)
        
        if format_type == 'plain_text':
            return PlainTextParser().parse(base_name, content_dir)
        elif format_type == 'legacy_html':
            return LegacyHTMLParser().parse(base_name, content_dir)
        elif format_type == 'modern_html':
            return ModernHTMLParser().parse(base_name, content_dir)
        else:
            raise ValueError(f"Unknown format: {format_type}")
```

### 3. Financial Data Validation
```python
def validate_financial_data(receipt_data):
    """Validate financial calculations across all formats."""
    subtotal = receipt_data.get('subtotal', 0)
    tax = receipt_data.get('tax', 0) 
    total = receipt_data.get('total', 0)
    
    # Check calculation (within $0.01 tolerance for rounding)
    if subtotal > 0 and tax >= 0:
        calculated_total = subtotal + tax
        if abs(calculated_total - total) > 0.01:
            logger.warning(f"Financial mismatch: {subtotal} + {tax} != {total}")
    
    return receipt_data
```

### 4. Error Handling Strategy
```python
# Graceful degradation with fallbacks
def extract_with_fallbacks(soup, selectors):
    """Try multiple selectors until one works."""
    for selector in selectors:
        try:
            result = soup.select_one(selector)
            if result and result.get_text().strip():
                return result.get_text().strip()
        except Exception:
            continue
    return None
```

## Corrected Implementation Recommendations

### 1. Three-Parser Architecture (Priority Order)
```python
class ReceiptParsingSystem:
    def __init__(self):
        self.parsers = {
            'plain_text': PlainTextParser(),      # 67.9% coverage
            'legacy_html': LegacyHTMLParser(),    # 26.3% coverage  
            'modern_html': ModernHTMLParser()     # 5.8% coverage
        }
    
    def parse_receipt(self, base_name, content_dir):
        format_type = detect_receipt_format(base_name, content_dir)
        parser = self.parsers.get(format_type)
        
        if not parser:
            raise ValueError(f"No parser for format: {format_type}")
            
        return parser.parse(base_name, content_dir)
```

### 2. Parser Implementation Order
1. **PlainTextParser**: Implement first - handles 222/327 receipts (67.9%)
2. **LegacyHTMLParser**: Implement second - handles 86/327 receipts (26.3%)
3. **ModernHTMLParser**: Implement last - handles 19/327 receipts (5.8%)

### 3. Testing Strategy
```python
# Test against known working examples
TEST_CASES = {
    'plain_text': [
        '20201104_071514_Your receipt from Apple__72b38622',  # 2020 example
        '20210719_104803_Your receipt from Apple__79cc30c7',  # 2021 example
    ],
    'legacy_html': [
        '20240916_034902_Your receipt from Apple__b7a09dca',  # 2024 HTML
    ],
    'modern_html': [
        '20250420_212800_Your receipt from Apple__172a0351',  # 2025 modern
    ]
}
```

This corrected approach will handle **100% of purchase receipts** with just three focused parsers instead of the complex multi-format system originally proposed.

### Universal JSON Output Schema
```json
{
  "format_detected": "modern_css",
  "apple_id": "***REMOVED***",
  "receipt_date": "2025-04-20",
  "order_id": "MSD2TWZNN6", 
  "document_number": "166943447141",
  "subtotal": 37.95,
  "tax": 1.94,
  "total": 39.89,
  "currency": "USD",
  "payment_method": "Apple Card",
  "billed_to": {
    "name": "Karl Davis",
    "address": "715 Longview Ave\nWestminster  MD 21157-5724\nUnited States"
  },
  "items": [
    {
      "title": "Apple One",
      "subtitle": "Premier (Monthly)",
      "type": "subscription",
      "artist": null,
      "device": null,
      "cost": 37.95,
      "selector_used": "p.custom-gzadzy"
    }
  ],
  "parsing_metadata": {
    "selectors_successful": ["p.custom-f41j3e", "p.custom-gzadzy"],
    "selectors_failed": [],
    "fallback_used": false
  }
}
```

## Parser Testing and Validation Strategy

### Selector Reliability Testing
```python
def test_selector_chains():
    formats = {
        'legacy_table': ['20201104_071514_Your receipt from Apple__72b38622.eml'],
        'semantic_table': ['20210719_104803_Your receipt from Apple__79cc30c7.eml'], 
        'modern_css': ['20250420_212800_Your receipt from Apple__172a0351.eml']
    }
    
    for format_type, examples in formats.items():
        for example in examples:
            test_all_selectors(example, format_type)
```

### Critical Validation Rules
1. **Financial Integrity**: 
   - `subtotal + tax = total` (±$0.01 tolerance for rounding)
   - All monetary values must parse as valid decimals
   - Currency symbols removed consistently

2. **Selector Fallback Testing**:
   - Primary selector success rate > 95%
   - Fallback selector coverage for remaining 5%
   - Text-based extraction as last resort

3. **Multi-Item Consistency**:
   - Sum of individual item costs = subtotal
   - Item count matches parsed item list length
   - Each item has required fields (title, cost)

### Cross-Format Field Mapping
```python
FIELD_SELECTORS = {
    'order_id': {
        'modern_css': 'p.custom-f41j3e:contains("Order ID:") + p.custom-zresjj',
        'semantic_table': 'span:contains("ORDER ID") + span',
        'legacy_table': 'span[style*="color:#0070c9"]'
    },
    'apple_id': {
        'modern_css': 'p.custom-f41j3e:contains("Apple Account:") + p.custom-zresjj', 
        'semantic_table': 'span:contains("APPLE ID") + text()',
        'legacy_table': 'td:contains("APPLE ID") + td'
    }
    # ... additional field mappings
}
```

### Parser Performance Targets
- **Coverage**: >95% of receipts successfully parsed
- **Accuracy**: >99% field extraction accuracy on known formats
- **Speed**: <100ms per receipt parsing time
- **Memory**: <10MB peak memory usage for batch processing

---

*Corrected analysis based on metadata extraction from 327 actual purchase receipts*  
*Key insight: Format differences are temporal evolution, not parallel systems*  
*Implementation priority: Plain Text (67.9%) → Legacy HTML (26.3%) → Modern HTML (5.8%)*
*Previous analysis was fundamentally flawed due to conflating purchase types with format types*
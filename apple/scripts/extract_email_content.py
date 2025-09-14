#!/usr/bin/env python3
"""
Extract plain text and HTML content from Apple receipt .eml files.

This script processes all .eml files in the Apple emails data directory and extracts:
1. Plain text versions (.txt files) 
2. Raw HTML versions (.html files)
3. Pretty-printed HTML versions (-formatted.html files)
4. Simplified HTML versions (-formatted-simple.html files)

The goal is to create clean, analyzable versions of each receipt for proper format analysis.
"""

import os
import sys
import email
import email.message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from bs4 import BeautifulSoup
import re
from typing import Optional, Tuple
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_script_dir() -> Path:
    """Get the directory containing this script."""
    return Path(__file__).parent

def get_data_dir() -> Path:
    """Get the Apple emails data directory."""
    script_dir = get_script_dir()
    data_dir = script_dir.parent / "data"
    
    # Find the most recent email data directory
    email_dirs = [d for d in data_dir.glob("*_apple_emails") if d.is_dir()]
    if not email_dirs:
        raise FileNotFoundError("No Apple email data directories found")
    
    # Return the most recent one (assuming date format in directory name)
    return max(email_dirs)

def extract_mime_parts(msg: email.message.Message) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract plain text and HTML parts from an email message.
    
    Returns:
        Tuple of (plain_text_content, html_content) where either may be None
    """
    plain_text = None
    html_content = None
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = part.get('Content-Disposition', '')
            
            # Skip attachments
            if 'attachment' in content_disposition:
                continue
                
            if content_type == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        plain_text = payload.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            plain_text = payload.decode('iso-8859-1')
                        except UnicodeDecodeError:
                            logger.warning(f"Could not decode plain text part")
                            
            elif content_type == 'text/html':
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        html_content = payload.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            html_content = payload.decode('iso-8859-1')
                        except UnicodeDecodeError:
                            logger.warning(f"Could not decode HTML part")
    else:
        # Single part message
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            try:
                content = payload.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = payload.decode('iso-8859-1')
                except UnicodeDecodeError:
                    logger.warning(f"Could not decode message content")
                    return None, None
            
            if content_type == 'text/plain':
                plain_text = content
            elif content_type == 'text/html':
                html_content = content
    
    return plain_text, html_content

def clean_html_attributes(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Remove visual formatting attributes while preserving semantic attributes.
    
    Removes: style, width, height, cellpadding, cellspacing, border, align, 
             valign, bgcolor, color, font attributes
    Preserves: class, id, colspan, rowspan, href, src, alt
    """
    # Attributes to remove (visual formatting)
    visual_attrs = {
        'style', 'width', 'height', 'cellpadding', 'cellspacing', 'border', 
        'align', 'valign', 'bgcolor', 'color', 'face', 'size', 'bordercolor',
        'marginheight', 'marginwidth', 'topmargin', 'leftmargin',
        'link', 'vlink', 'alink', 'text'
    }
    
    # Remove style blocks entirely
    for style_tag in soup.find_all('style'):
        style_tag.decompose()
    
    # Remove visual attributes from all tags
    for tag in soup.find_all():
        attrs_to_remove = []
        for attr in tag.attrs:
            if attr in visual_attrs:
                attrs_to_remove.append(attr)
        
        for attr in attrs_to_remove:
            del tag.attrs[attr]
    
    return soup

def pretty_print_html(html_content: str) -> str:
    """Pretty print HTML with proper indentation, no width wrapping."""
    soup = BeautifulSoup(html_content, 'lxml')
    return soup.prettify()

def simplify_html(html_content: str) -> str:
    """Create simplified HTML with visual attributes removed."""
    soup = BeautifulSoup(html_content, 'lxml')
    cleaned_soup = clean_html_attributes(soup)
    return cleaned_soup.prettify()

def process_eml_file(eml_path: Path, output_dir: Path) -> dict:
    """
    Process a single .eml file and extract all content versions.
    
    Returns a dict with extraction results.
    """
    logger.info(f"Processing {eml_path.name}")
    
    # Parse the email
    with open(eml_path, 'rb') as f:
        msg = email.message_from_bytes(f.read())
    
    base_name = eml_path.stem  # filename without .eml extension
    results = {
        'eml_file': eml_path.name,
        'has_plain_text': False,
        'has_html': False,
        'plain_text_file': None,
        'html_file': None,
        'formatted_html_file': None,
        'simplified_html_file': None,
        'errors': []
    }
    
    try:
        # Extract MIME parts
        plain_text, html_content = extract_mime_parts(msg)
        
        # Save plain text version if available
        if plain_text:
            txt_path = output_dir / f"{base_name}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(plain_text)
            results['has_plain_text'] = True
            results['plain_text_file'] = txt_path.name
            logger.debug(f"  → Saved plain text: {txt_path.name}")
        
        # Save HTML versions if available
        if html_content:
            # Raw HTML
            html_path = output_dir / f"{base_name}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            results['has_html'] = True
            results['html_file'] = html_path.name
            logger.debug(f"  → Saved raw HTML: {html_path.name}")
            
            # Pretty-printed HTML
            try:
                formatted_html = pretty_print_html(html_content)
                formatted_path = output_dir / f"{base_name}-formatted.html"
                with open(formatted_path, 'w', encoding='utf-8') as f:
                    f.write(formatted_html)
                results['formatted_html_file'] = formatted_path.name
                logger.debug(f"  → Saved formatted HTML: {formatted_path.name}")
            except Exception as e:
                results['errors'].append(f"Failed to create formatted HTML: {str(e)}")
                logger.warning(f"  × Failed to format HTML: {e}")
            
            # Simplified HTML
            try:
                simplified_html = simplify_html(html_content)
                simplified_path = output_dir / f"{base_name}-formatted-simple.html"
                with open(simplified_path, 'w', encoding='utf-8') as f:
                    f.write(simplified_html)
                results['simplified_html_file'] = simplified_path.name
                logger.debug(f"  → Saved simplified HTML: {simplified_path.name}")
            except Exception as e:
                results['errors'].append(f"Failed to create simplified HTML: {str(e)}")
                logger.warning(f"  × Failed to simplify HTML: {e}")
                
    except Exception as e:
        error_msg = f"Failed to process {eml_path.name}: {str(e)}"
        results['errors'].append(error_msg)
        logger.error(f"  × {error_msg}")
    
    return results

def main():
    """Main function to process all .eml files."""
    try:
        # Get directories
        data_dir = get_data_dir()
        logger.info(f"Using data directory: {data_dir}")
        
        # Create output directory for extracted content
        output_dir = data_dir / "extracted_content"
        output_dir.mkdir(exist_ok=True)
        logger.info(f"Output directory: {output_dir}")
        
        # Find all .eml files
        eml_files = list(data_dir.glob("*.eml"))
        if not eml_files:
            logger.error("No .eml files found in data directory")
            return 1
        
        logger.info(f"Found {len(eml_files)} .eml files to process")
        
        # Process each file
        results = []
        for eml_path in sorted(eml_files):
            result = process_eml_file(eml_path, output_dir)
            results.append(result)
        
        # Summary statistics
        plain_text_count = sum(1 for r in results if r['has_plain_text'])
        html_count = sum(1 for r in results if r['has_html'])
        error_count = sum(1 for r in results if r['errors'])
        
        logger.info("\n" + "="*50)
        logger.info("EXTRACTION SUMMARY")
        logger.info("="*50)
        logger.info(f"Total files processed: {len(results)}")
        logger.info(f"Files with plain text: {plain_text_count}")
        logger.info(f"Files with HTML: {html_count}")
        logger.info(f"Files with errors: {error_count}")
        
        if error_count > 0:
            logger.warning("\nFiles with errors:")
            for result in results:
                if result['errors']:
                    logger.warning(f"  {result['eml_file']}: {result['errors']}")
        
        # Check if we have universal plain text coverage
        if plain_text_count == len(results):
            logger.info("\n✓ ALL emails have plain text versions - can use plain text parsing!")
        elif plain_text_count == 0:
            logger.info("\n✗ NO emails have plain text versions - must use HTML parsing")
        else:
            logger.info(f"\n~ {plain_text_count}/{len(results)} emails have plain text - hybrid approach needed")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to process emails: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
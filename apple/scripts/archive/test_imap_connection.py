#!/usr/bin/env python3
"""
Test IMAP connection and basic email search.

This script helps verify that IMAP credentials are working before running
the full analysis.

Usage:
    # Create .env file with credentials (see .env.template)
    uv run python apple/scripts/test_imap_connection.py
"""

import imaplib
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)


def test_connection():
    """Test IMAP connection and list folders."""
    server = os.environ.get('IMAP_SERVER')
    username = os.environ.get('IMAP_USERNAME')
    password = os.environ.get('IMAP_PASSWORD')
    
    if not all([server, username, password]):
        print("Error: Missing IMAP credentials")
        print("\nPlease create a .env file with:")
        print("  IMAP_SERVER='your.email.server'")
        print("  IMAP_USERNAME='your@email.com'")
        print("  IMAP_PASSWORD='your_password'")
        print("\nSee .env.template for an example.")
        print("\nCommon IMAP servers:")
        print("  - Gmail: imap.gmail.com")
        print("  - Outlook: outlook.office365.com")
        print("  - iCloud: imap.mail.me.com")
        print("  - Yahoo: imap.mail.yahoo.com")
        return False
    
    print(f"Testing connection to {server}...")
    print(f"Username: {username}")
    print("-" * 40)
    
    try:
        # Try to connect
        mail = imaplib.IMAP4_SSL(server, 993)
        print("✓ Connected to server")
        
        # Try to login
        mail.login(username, password)
        print("✓ Authentication successful")
        
        # List folders
        result, folders = mail.list()
        if result == 'OK':
            print(f"✓ Found {len(folders)} folders")
            print("\nAvailable folders:")
            for folder in folders[:10]:  # Show first 10
                print(f"  - {folder.decode()}")
            if len(folders) > 10:
                print(f"  ... and {len(folders) - 10} more")
        
        # Try a simple search in INBOX
        mail.select('INBOX')
        result, data = mail.search(None, '(FROM "apple.com")')
        if result == 'OK':
            count = len(data[0].split()) if data[0] else 0
            print(f"\n✓ Test search successful")
            print(f"  Found {count} emails from apple.com")
        
        mail.logout()
        print("\n✅ All tests passed! IMAP connection is working.")
        return True
        
    except imaplib.IMAP4.error as e:
        print(f"\n❌ IMAP error: {e}")
        print("\nPossible issues:")
        print("  - Wrong username/password")
        print("  - IMAP not enabled for this account")
        print("  - Need app-specific password (for Gmail/iCloud)")
        return False
        
    except Exception as e:
        print(f"\n❌ Connection error: {e}")
        print("\nPossible issues:")
        print("  - Wrong server address")
        print("  - Network/firewall blocking connection")
        print("  - Server requires different port")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
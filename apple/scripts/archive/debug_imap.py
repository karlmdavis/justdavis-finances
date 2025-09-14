#!/usr/bin/env python3
"""
Debug IMAP connection with more detailed error information.
"""

import imaplib
import os
import ssl
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Enable IMAP debug output
imaplib.Debug = 4

def test_connection():
    server = os.environ.get('IMAP_SERVER')
    username = os.environ.get('IMAP_USERNAME')
    password = os.environ.get('IMAP_PASSWORD')
    
    if not all([server, username, password]):
        print("Missing credentials in .env file")
        return
    
    print(f"Attempting connection to {server}:993")
    print(f"Username: {username}")
    print(f"Password length: {len(password)} characters")
    print("-" * 40)
    
    try:
        # Create SSL context
        context = ssl.create_default_context()
        
        print("Creating IMAP4_SSL connection...")
        mail = imaplib.IMAP4_SSL(server, 993, ssl_context=context)
        print("✓ SSL connection established")
        
        print(f"\nAttempting login with username: {username}")
        mail.login(username, password)
        print("✓ Login successful!")
        
        # Get capabilities
        print("\nServer capabilities:")
        capability_response = mail.capability()
        print(f"  {capability_response[1][0].decode()}")
        
        mail.logout()
        return True
        
    except imaplib.IMAP4.error as e:
        print(f"\n❌ IMAP protocol error: {e}")
        print("\nThis usually means:")
        print("  - Wrong username format (try with/without @domain)")
        print("  - Wrong password")
        print("  - Account requires app-specific password")
        
    except ssl.SSLError as e:
        print(f"\n❌ SSL error: {e}")
        print("\nThis usually means:")
        print("  - Server doesn't support SSL on port 993")
        print("  - Certificate issues")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
    
    return False


if __name__ == "__main__":
    print("IMAP Debug Tool")
    print("=" * 40)
    test_connection()
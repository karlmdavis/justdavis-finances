#!/usr/bin/env python3
"""
Fetch Apple receipt emails from IMAP server and save as .eml files.

This script downloads all Apple receipt emails and saves them locally for
processing. It supports resume on interruption and retry logic for reliability.

Usage:
    # Create .env file with credentials (see .env.template)
    uv run python apple/scripts/fetch_receipt_emails.py
"""

import imaplib
import email
from email.message import Message
import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from typing import List, Set, Optional
import hashlib
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)


class EmailFetcher:
    """Fetches Apple receipt emails with retry logic and resume capability."""
    
    def __init__(self, output_dir: str = "apple/data"):
        self.output_dir = Path(output_dir)
        self.session_dir = None
        self.mail = None
        self.checkpoint_file = None
        self.processed_ids = set()
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
    def connect(self) -> bool:
        """Connect to IMAP server with retry logic."""
        server = os.environ.get('IMAP_SERVER')
        username = os.environ.get('IMAP_USERNAME')
        password = os.environ.get('IMAP_PASSWORD')
        
        if not all([server, username, password]):
            print("Error: Missing IMAP credentials")
            print("Please create a .env file with IMAP_SERVER, IMAP_USERNAME, and IMAP_PASSWORD")
            print("See .env.template for an example.")
            return False
        
        for attempt in range(self.max_retries):
            try:
                print(f"Connecting to {server} (attempt {attempt + 1}/{self.max_retries})...")
                self.mail = imaplib.IMAP4_SSL(server, 993)
                self.mail.login(username, password)
                print("Successfully connected to IMAP server")
                return True
            except Exception as e:
                print(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    print(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    print("Max retries exceeded. Connection failed.")
                    return False
        return False
    
    def setup_session(self):
        """Create session directory and checkpoint file."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_dir = self.output_dir / f"{timestamp}_apple_emails"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        self.checkpoint_file = self.session_dir / "checkpoint.json"
        
        # Load existing checkpoint if it exists
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                self.processed_ids = set(checkpoint.get('processed_ids', []))
                print(f"Resuming from checkpoint: {len(self.processed_ids)} emails already processed")
    
    def save_checkpoint(self):
        """Save current progress to checkpoint file."""
        checkpoint = {
            'processed_ids': list(self.processed_ids),
            'timestamp': datetime.now().isoformat()
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def search_receipt_emails(self) -> List[bytes]:
        """Search for Apple receipt emails."""
        search_patterns = [
            'SUBJECT "Your receipt from Apple"',
            'SUBJECT "Receipt from Apple"',
            'FROM "no_reply@email.apple.com"',
        ]
        
        all_ids = set()
        
        for pattern in search_patterns:
            try:
                print(f"Searching: {pattern}")
                self.mail.select('INBOX')
                result, data = self.mail.search(None, pattern)
                
                if result == 'OK' and data[0]:
                    ids = data[0].split()
                    all_ids.update(ids)
                    print(f"  Found {len(ids)} emails")
                    
            except Exception as e:
                print(f"Search error for '{pattern}': {e}")
        
        # Remove already processed IDs
        new_ids = [id for id in all_ids if id.decode() not in self.processed_ids]
        
        print(f"\nTotal unique emails found: {len(all_ids)}")
        print(f"Already processed: {len(self.processed_ids)}")
        print(f"New emails to fetch: {len(new_ids)}")
        
        return new_ids
    
    def fetch_email(self, email_id: bytes) -> Optional[Message]:
        """Fetch a single email with retry logic."""
        for attempt in range(self.max_retries):
            try:
                result, data = self.mail.fetch(email_id, '(RFC822)')
                if result == 'OK':
                    raw_email = data[0][1]
                    return email.message_from_bytes(raw_email)
            except Exception as e:
                print(f"  Fetch attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    # Try to reconnect if connection was lost
                    try:
                        self.mail.select('INBOX')
                    except:
                        self.connect()
                        self.mail.select('INBOX')
        return None
    
    def save_email(self, msg: Message, email_id: str) -> bool:
        """Save email as .eml file."""
        try:
            # Extract metadata for filename
            subject = msg.get('Subject', 'no_subject')
            date_str = msg.get('Date', '')
            
            # Parse date for filename
            try:
                date_tuple = email.utils.parsedate_to_datetime(date_str)
                date_prefix = date_tuple.strftime("%Y%m%d_%H%M%S")
            except:
                date_prefix = "unknown_date"
            
            # Create safe filename
            safe_subject = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' 
                                 for c in subject)[:50]
            
            # Use email ID hash for uniqueness
            id_hash = hashlib.md5(email_id.encode()).hexdigest()[:8]
            
            filename = f"{date_prefix}_{safe_subject}_{id_hash}.eml"
            filepath = self.session_dir / filename
            
            # Save email
            with open(filepath, 'wb') as f:
                f.write(msg.as_bytes())
            
            return True
            
        except Exception as e:
            print(f"  Error saving email: {e}")
            return False
    
    def fetch_all(self):
        """Main fetch process."""
        if not self.connect():
            return False
        
        self.setup_session()
        
        try:
            # Search for emails
            email_ids = self.search_receipt_emails()
            
            if not email_ids:
                print("No new emails to fetch.")
                return True
            
            # Fetch each email
            print(f"\nFetching {len(email_ids)} emails...")
            print("-" * 40)
            
            success_count = 0
            error_count = 0
            
            for i, email_id in enumerate(email_ids, 1):
                email_id_str = email_id.decode()
                
                print(f"[{i}/{len(email_ids)}] Fetching email {email_id_str}...", end='')
                
                # Fetch email
                msg = self.fetch_email(email_id)
                
                if msg:
                    # Save email
                    if self.save_email(msg, email_id_str):
                        self.processed_ids.add(email_id_str)
                        success_count += 1
                        print(" ✓")
                    else:
                        error_count += 1
                        print(" ✗ (save failed)")
                else:
                    error_count += 1
                    print(" ✗ (fetch failed)")
                
                # Save checkpoint periodically
                if i % 10 == 0:
                    self.save_checkpoint()
            
            # Final checkpoint save
            self.save_checkpoint()
            
            print("\n" + "=" * 40)
            print("Fetch Summary:")
            print(f"  Successfully fetched: {success_count}")
            print(f"  Errors: {error_count}")
            print(f"  Emails saved to: {self.session_dir}")
            
            # Create summary file
            summary_file = self.session_dir / "summary.json"
            summary = {
                'fetch_date': datetime.now().isoformat(),
                'total_fetched': success_count,
                'errors': error_count,
                'email_ids': list(self.processed_ids)
            }
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"\nFetch process error: {e}")
            return False
            
        finally:
            if self.mail:
                try:
                    self.mail.logout()
                except:
                    pass


def main():
    """Main entry point."""
    print("=" * 60)
    print("Apple Receipt Email Fetcher")
    print("=" * 60)
    
    # Check for limit override
    limit = os.environ.get('APPLE_EMAIL_LIMIT')
    if limit:
        print(f"Note: Email limit set to {limit}")
    
    fetcher = EmailFetcher()
    success = fetcher.fetch_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
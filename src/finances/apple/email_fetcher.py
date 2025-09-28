#!/usr/bin/env python3
"""
Apple Email Fetcher Module

Professional email fetching for Apple receipts with IMAP support.
Handles secure email access and receipt email filtering.
"""

import imaplib
import email
import email.message
import email.header
import email.utils
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

from ..core.config import get_config
from ..core.json_utils import write_json

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Configuration for email fetching."""
    imap_server: str
    imap_port: int
    username: str
    password: str
    use_oauth: bool = False
    search_folders: List[str] = field(default_factory=lambda: ["INBOX", "[Gmail]/All Mail"])


@dataclass
class AppleReceiptEmail:
    """Represents an Apple receipt email."""
    message_id: str
    subject: str
    sender: str
    date: datetime
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    raw_content: Optional[str] = None
    folder: str = "INBOX"
    metadata: Dict[str, Any] = field(default_factory=dict)


class AppleEmailFetcher:
    """
    Fetches Apple receipt emails from IMAP servers.

    Supports secure authentication and comprehensive email filtering
    to identify Apple Store, iTunes, and App Store receipts.
    """

    def __init__(self, config: Optional[EmailConfig] = None):
        """Initialize with email configuration."""
        if config is None:
            # Load from application config
            app_config = get_config()
            self.config = EmailConfig(
                imap_server=app_config.email.imap_server,
                imap_port=app_config.email.imap_port,
                username=app_config.email.username or "",
                password=app_config.email.password or "",
                use_oauth=app_config.email.use_oauth,
                search_folders=app_config.email.email_search_folders
            )
        else:
            self.config = config

        self.connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> bool:
        """
        Connect to IMAP server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to IMAP server: {self.config.imap_server}:{self.config.imap_port}")

            self.connection = imaplib.IMAP4_SSL(
                self.config.imap_server,
                self.config.imap_port
            )

            if self.config.use_oauth:
                # OAuth2 authentication would go here
                logger.error("OAuth2 authentication not yet implemented")
                return False
            else:
                # Basic authentication
                self.connection.login(self.config.username, self.config.password)

            logger.info("Successfully connected to IMAP server")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from IMAP server."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.connection = None

    def fetch_apple_receipts(
        self,
        days_back: int = 90,
        max_emails: Optional[int] = None
    ) -> List[AppleReceiptEmail]:
        """
        Fetch Apple receipt emails from configured folders.

        Args:
            days_back: Number of days to search back
            max_emails: Maximum number of emails to fetch (None for no limit)

        Returns:
            List of AppleReceiptEmail objects
        """
        if not self.connection:
            if not self.connect():
                logger.error("Cannot fetch emails without connection")
                return []

        all_receipts = []

        try:
            for folder in self.config.search_folders:
                logger.info(f"Searching folder: {folder}")

                try:
                    # Select folder
                    result, _ = self.connection.select(folder, readonly=True)
                    if result != 'OK':
                        logger.warning(f"Cannot select folder {folder}")
                        continue

                    # Search for Apple receipt emails
                    receipts = self._search_apple_receipts_in_folder(
                        folder, days_back, max_emails
                    )

                    all_receipts.extend(receipts)
                    logger.info(f"Found {len(receipts)} receipts in {folder}")

                    if max_emails and len(all_receipts) >= max_emails:
                        all_receipts = all_receipts[:max_emails]
                        break

                except Exception as e:
                    logger.error(f"Error searching folder {folder}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error during email fetching: {e}")

        logger.info(f"Total Apple receipts found: {len(all_receipts)}")
        return all_receipts

    def _search_apple_receipts_in_folder(
        self,
        folder: str,
        days_back: int,
        max_emails: Optional[int]
    ) -> List[AppleReceiptEmail]:
        """Search for Apple receipts in a specific folder."""
        receipts = []

        try:
            # Calculate date range for search
            cutoff_date = datetime.now() - timedelta(days=days_back)
            date_string = cutoff_date.strftime("%d-%b-%Y")

            # Build search criteria for Apple receipts
            search_criteria = self._build_apple_search_criteria(date_string)

            logger.debug(f"Search criteria: {search_criteria}")

            # Search for emails
            result, message_numbers = self.connection.search(None, *search_criteria)

            if result != 'OK':
                logger.warning(f"Search failed in folder {folder}")
                return receipts

            # Process found emails
            if message_numbers and message_numbers[0]:
                msg_nums = message_numbers[0].split()
                logger.info(f"Found {len(msg_nums)} potential Apple emails in {folder}")

                # Limit the number of emails to process
                if max_emails:
                    msg_nums = msg_nums[-max_emails:]  # Get most recent

                for msg_num in msg_nums:
                    try:
                        receipt = self._fetch_and_parse_email(msg_num.decode(), folder)
                        if receipt and self._is_apple_receipt(receipt):
                            receipts.append(receipt)
                    except Exception as e:
                        logger.warning(f"Error processing email {msg_num}: {e}")

        except Exception as e:
            logger.error(f"Error searching folder {folder}: {e}")

        return receipts

    def _build_apple_search_criteria(self, since_date: str) -> List[str]:
        """Build IMAP search criteria for Apple receipts."""
        # Search for emails from Apple domains since the cutoff date
        apple_domains = [
            'apple.com',
            'itunes.com',
            'icloud.com',
            'me.com',
            'mac.com'
        ]

        criteria = [f'(SINCE {since_date})']

        # Add sender criteria for Apple domains
        from_criteria = []
        for domain in apple_domains:
            from_criteria.append(f'(FROM {domain})')

        if from_criteria:
            criteria.append(f'(OR {" ".join(from_criteria)})')

        # Add subject criteria for receipt-related terms
        receipt_terms = [
            'receipt',
            'Your receipt from Apple',
            'iTunes Store',
            'App Store',
            'Apple Store'
        ]

        subject_criteria = []
        for term in receipt_terms:
            subject_criteria.append(f'(SUBJECT "{term}")')

        if subject_criteria:
            criteria.append(f'(OR {" ".join(subject_criteria)})')

        return criteria

    def _fetch_and_parse_email(self, msg_num: str, folder: str) -> Optional[AppleReceiptEmail]:
        """Fetch and parse a single email."""
        try:
            # Fetch email data
            result, msg_data = self.connection.fetch(msg_num, '(RFC822)')

            if result != 'OK' or not msg_data or not msg_data[0]:
                return None

            # Parse email message
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Extract basic information
            subject = self._decode_header(msg.get('Subject', ''))
            sender = self._decode_header(msg.get('From', ''))
            date_str = msg.get('Date', '')
            message_id = msg.get('Message-ID', f'{folder}_{msg_num}')

            # Parse date
            try:
                email_date = email.utils.parsedate_to_datetime(date_str)
            except Exception:
                email_date = datetime.now()

            # Extract email content
            html_content, text_content = self._extract_email_content(msg)

            # Create receipt email object
            receipt_email = AppleReceiptEmail(
                message_id=message_id,
                subject=subject,
                sender=sender,
                date=email_date,
                html_content=html_content,
                text_content=text_content,
                raw_content=raw_email.decode('utf-8', errors='ignore'),
                folder=folder,
                metadata={
                    'msg_num': msg_num,
                    'size': len(raw_email)
                }
            )

            return receipt_email

        except Exception as e:
            logger.error(f"Error fetching email {msg_num}: {e}")
            return None

    def _extract_email_content(self, msg: email.message.Message) -> Tuple[Optional[str], Optional[str]]:
        """Extract HTML and text content from email message."""
        html_content = None
        text_content = None

        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))

                    # Skip attachments
                    if 'attachment' in content_disposition:
                        continue

                    if content_type == 'text/html':
                        html_payload = part.get_payload(decode=True)
                        if html_payload:
                            html_content = html_payload.decode('utf-8', errors='ignore')

                    elif content_type == 'text/plain':
                        text_payload = part.get_payload(decode=True)
                        if text_payload:
                            text_content = text_payload.decode('utf-8', errors='ignore')

            else:
                # Single part message
                content_type = msg.get_content_type()
                payload = msg.get_payload(decode=True)

                if payload:
                    content = payload.decode('utf-8', errors='ignore')

                    if content_type == 'text/html':
                        html_content = content
                    elif content_type == 'text/plain':
                        text_content = content

        except Exception as e:
            logger.error(f"Error extracting email content: {e}")

        return html_content, text_content

    def _decode_header(self, header: str) -> str:
        """Decode email header with proper encoding handling."""
        if not header:
            return ''

        try:
            decoded_header = email.header.decode_header(header)
            decoded_parts = []

            for part, encoding in decoded_header:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_parts.append(part.decode(encoding, errors='ignore'))
                    else:
                        decoded_parts.append(part.decode('utf-8', errors='ignore'))
                else:
                    decoded_parts.append(str(part))

            return ''.join(decoded_parts)

        except Exception as e:
            logger.warning(f"Error decoding header {header}: {e}")
            return header

    def _is_apple_receipt(self, email_obj: AppleReceiptEmail) -> bool:
        """
        Determine if an email is actually an Apple receipt.

        Performs additional filtering beyond the initial search to ensure
        we only process genuine Apple receipt emails.
        """
        # Check sender domain
        apple_senders = [
            '@apple.com',
            '@itunes.com',
            '@icloud.com',
            'noreply@email.apple.com',
            'do_not_reply@itunes.com'
        ]

        sender_check = any(domain in email_obj.sender.lower() for domain in apple_senders)
        if not sender_check:
            logger.debug(f"Sender check failed for: {email_obj.sender}")
            return False

        # Check subject for receipt indicators
        subject_lower = email_obj.subject.lower()
        receipt_indicators = [
            'receipt',
            'your receipt from apple',
            'thank you for your purchase',
            'itunes store',
            'app store',
            'apple store'
        ]

        subject_check = any(indicator in subject_lower for indicator in receipt_indicators)
        if not subject_check:
            logger.debug(f"Subject check failed for: {email_obj.subject}")
            return False

        # Check content for purchase indicators
        content_to_check = (email_obj.html_content or '') + (email_obj.text_content or '')
        content_lower = content_to_check.lower()

        content_indicators = [
            'total',
            'order id',
            'document no',
            'purchase',
            'download',
            'subscription',
            '$', '£', '€', '¥'  # Currency symbols
        ]

        content_check = any(indicator in content_lower for indicator in content_indicators)
        if not content_check:
            logger.debug(f"Content check failed for: {email_obj.message_id}")
            return False

        # Exclude promotional/non-receipt emails
        exclusion_terms = [
            'promotional',
            'marketing',
            'newsletter',
            'survey',
            'feedback',
            'update your',
            'privacy policy',
            'terms of service'
        ]

        exclusion_check = any(term in content_lower for term in exclusion_terms)
        if exclusion_check:
            logger.debug(f"Exclusion check triggered for: {email_obj.subject}")
            return False

        logger.debug(f"Email passed all checks: {email_obj.subject}")
        return True

    def save_emails_to_disk(
        self,
        emails: List[AppleReceiptEmail],
        output_dir: Path,
        format_html: bool = True
    ) -> Dict[str, Any]:
        """
        Save fetched emails to disk for processing.

        Args:
            emails: List of AppleReceiptEmail objects
            output_dir: Directory to save emails
            format_html: Whether to format HTML content

        Returns:
            Dictionary with save statistics
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        stats = {
            'total_emails': len(emails),
            'saved_successfully': 0,
            'save_errors': 0,
            'files_created': []
        }

        for i, email_obj in enumerate(emails):
            try:
                # Create base filename from email metadata
                safe_subject = re.sub(r'[^\w\-_\.]', '_', email_obj.subject)[:50]
                base_name = f"{email_obj.date.strftime('%Y%m%d_%H%M%S')}_{safe_subject}_{i:03d}"

                # Save HTML content if available
                if email_obj.html_content and format_html:
                    html_file = output_dir / f"{base_name}-formatted-simple.html"
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(email_obj.html_content)
                    stats['files_created'].append(str(html_file))

                # Save text content if available
                if email_obj.text_content:
                    text_file = output_dir / f"{base_name}.txt"
                    with open(text_file, 'w', encoding='utf-8') as f:
                        f.write(email_obj.text_content)
                    stats['files_created'].append(str(text_file))

                # Save raw email
                raw_file = output_dir / f"{base_name}.eml"
                with open(raw_file, 'w', encoding='utf-8') as f:
                    f.write(email_obj.raw_content or '')
                stats['files_created'].append(str(raw_file))

                # Save metadata
                metadata_file = output_dir / f"{base_name}_metadata.json"
                metadata = {
                    'message_id': email_obj.message_id,
                    'subject': email_obj.subject,
                    'sender': email_obj.sender,
                    'date': email_obj.date.isoformat(),
                    'folder': email_obj.folder,
                    'metadata': email_obj.metadata
                }

                write_json(metadata_file, metadata)
                stats['files_created'].append(str(metadata_file))

                stats['saved_successfully'] += 1

            except Exception as e:
                logger.error(f"Error saving email {i}: {e}")
                stats['save_errors'] += 1

        logger.info(f"Saved {stats['saved_successfully']}/{stats['total_emails']} emails to {output_dir}")
        return stats


def fetch_apple_receipts_cli(
    days_back: int = 90,
    output_dir: Optional[Path] = None,
    max_emails: Optional[int] = None
) -> None:
    """
    CLI function to fetch Apple receipts.

    Args:
        days_back: Number of days to search back
        output_dir: Directory to save emails (uses config default if None)
        max_emails: Maximum number of emails to fetch
    """
    config = get_config()

    if output_dir is None:
        output_dir = config.data_dir / "apple" / "emails"

    # Verify email configuration
    if not config.email.username or not config.email.password:
        logger.error("Email credentials not configured. Check EMAIL_USERNAME and EMAIL_PASSWORD environment variables.")
        return

    # Initialize fetcher and fetch emails
    fetcher = AppleEmailFetcher()

    try:
        emails = fetcher.fetch_apple_receipts(days_back=days_back, max_emails=max_emails)

        if emails:
            stats = fetcher.save_emails_to_disk(emails, output_dir)
            logger.info(f"Fetch complete: {stats}")
        else:
            logger.info("No Apple receipt emails found")

    except Exception as e:
        logger.error(f"Error during email fetch: {e}")

    finally:
        fetcher.disconnect()
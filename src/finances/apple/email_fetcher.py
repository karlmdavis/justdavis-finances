#!/usr/bin/env python3
"""
Apple Email Fetcher Module

Professional email fetching for Apple receipts with IMAP support.
Handles secure email access and receipt email filtering.
"""

import email
import email.header
import email.message
import email.utils
import imaplib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

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


@dataclass
class AppleReceiptEmail:
    """Represents an Apple receipt email."""

    message_id: str
    subject: str
    sender: str
    date: datetime
    html_content: str | None = None
    text_content: str | None = None
    raw_content: str | None = None
    folder: str = "INBOX"
    metadata: dict[str, Any] = field(default_factory=dict)


class AppleEmailFetcher:
    """
    Fetches Apple receipt emails from IMAP servers.

    Supports secure authentication and comprehensive email filtering
    to identify Apple Store, iTunes, and App Store receipts.
    """

    def __init__(self, config: EmailConfig | None = None):
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
            )
        else:
            self.config = config

        self.connection: imaplib.IMAP4_SSL | None = None

    def connect(self) -> bool:
        """
        Connect to IMAP server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to IMAP server: {self.config.imap_server}:{self.config.imap_port}")

            self.connection = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)

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

    def _list_all_folders(self) -> list[str]:
        """
        List all IMAP folders recursively.

        Returns:
            List of folder names that can be searched
        """
        if not self.connection:
            logger.warning("Cannot list folders without connection")
            return []

        try:
            result, folders = self.connection.list()
            if result != "OK":
                logger.warning("Failed to list IMAP folders")
                return []

            folder_names = []
            for folder in folders:
                try:
                    # IMAP folder response format: b'(\\HasNoChildren) "/" "INBOX"'
                    # or: b'(\\HasNoChildren \\UnMarked) "." "Follow Up"'
                    if not isinstance(folder, bytes):
                        continue
                    folder_str = folder.decode()

                    # Use regex to extract folder name - everything after the delimiter
                    match = re.search(r'\([^)]+\)\s+"[^"]*"\s+(.+)', folder_str)
                    if match:
                        folder_name = match.group(1).strip()
                        # Remove quotes if present
                        if folder_name.startswith('"') and folder_name.endswith('"'):
                            folder_name = folder_name[1:-1]

                        # Skip malformed or system folders
                        if folder_name and folder_name not in ["."]:
                            folder_names.append(folder_name)
                except Exception as e:
                    logger.debug(f"Error parsing folder: {e}")
                    continue

            logger.info(f"Discovered {len(folder_names)} IMAP folders")
            return folder_names

        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []

    def fetch_apple_receipts(self) -> list[AppleReceiptEmail]:
        """
        Fetch all Apple receipt emails from all IMAP folders (recursive search).

        Returns:
            List of AppleReceiptEmail objects
        """
        if not self.connection and not self.connect():
            logger.error("Cannot fetch emails without connection")
            return []

        all_receipts = []
        folder_results: dict[str, int] = {}

        try:
            # Discover all folders recursively
            all_folders = self._list_all_folders()
            logger.info(f"Searching {len(all_folders)} folders for Apple receipts")

            for folder in all_folders:
                logger.debug(f"Searching folder: {folder}")

                try:
                    # Select folder - check connection exists
                    if not self.connection:
                        logger.warning("Connection lost")
                        break

                    # Try different folder name formats for compatibility
                    folder_attempts = [folder]
                    if " " in folder or "." in folder:
                        folder_attempts.append(f'"{folder}"')

                    selected = False
                    for attempt_name in folder_attempts:
                        try:
                            result, _ = self.connection.select(attempt_name, readonly=True)
                            if result == "OK":
                                selected = True
                                break
                        except Exception as e:
                            logger.debug(f"Cannot select folder '{attempt_name}': {e}")
                            continue

                    if not selected:
                        logger.debug(f"Cannot select folder '{folder}', skipping")
                        continue

                    # Search for Apple receipt emails
                    receipts = self._search_apple_receipts_in_folder(folder)

                    if receipts:
                        all_receipts.extend(receipts)
                        folder_results[folder] = len(receipts)
                        logger.info(f"Found {len(receipts)} receipts in '{folder}'")

                except Exception as e:
                    logger.debug(f"Error searching folder {folder}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error during email fetching: {e}")

        # Log summary by folder
        if folder_results:
            logger.info("Apple receipts found by folder:")
            for folder, count in sorted(folder_results.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {folder}: {count} emails")

        logger.info(f"Total Apple receipts found: {len(all_receipts)}")
        return all_receipts

    def _search_apple_receipts_in_folder(self, folder: str) -> list[AppleReceiptEmail]:
        """Search for all Apple receipts in a specific folder."""
        receipts: list[AppleReceiptEmail] = []

        try:
            # Use simple search patterns that work with all IMAP servers
            # Run multiple searches and combine unique results
            search_patterns = [
                'SUBJECT "Your receipt from Apple"',
                'SUBJECT "Receipt from Apple"',
                'FROM "no_reply@email.apple.com"',
            ]

            all_msg_ids: set[bytes] = set()

            # Check connection exists
            if not self.connection:
                logger.warning("Connection lost")
                return receipts

            # Execute each search pattern and collect unique message IDs
            for pattern in search_patterns:
                try:
                    result, message_numbers = self.connection.search(None, pattern)
                    if result == "OK" and message_numbers and message_numbers[0]:
                        msg_ids = message_numbers[0].split()
                        all_msg_ids.update(msg_ids)
                except Exception as e:
                    logger.debug(f"Search error for '{pattern}': {e}")
                    continue

            if not all_msg_ids:
                return receipts

            logger.info(f"Found {len(all_msg_ids)} potential Apple emails in {folder}")

            # Process found emails
            for msg_num in all_msg_ids:
                try:
                    receipt = self._fetch_and_parse_email(msg_num.decode(), folder)
                    if receipt and self._is_apple_receipt(receipt):
                        receipts.append(receipt)
                except Exception as e:
                    logger.warning(f"Error processing email {msg_num.decode()}: {e}")

        except Exception as e:
            logger.error(f"Error searching folder {folder}: {e}")

        return receipts

    def _fetch_and_parse_email(self, msg_num: str, folder: str) -> AppleReceiptEmail | None:
        """Fetch and parse a single email."""
        try:
            # Fetch email data - check connection exists
            if not self.connection:
                logger.warning("Connection lost")
                return None
            result, msg_data = self.connection.fetch(msg_num, "(RFC822)")

            if result != "OK" or not msg_data or not msg_data[0]:
                return None

            # Parse email message
            raw_email_data = msg_data[0][1]
            if not isinstance(raw_email_data, bytes):
                logger.warning(f"Expected bytes but got {type(raw_email_data)}")
                return None
            raw_email = raw_email_data
            msg = email.message_from_bytes(raw_email)

            # Extract basic information
            subject = self._decode_header(msg.get("Subject", ""))
            sender = self._decode_header(msg.get("From", ""))
            date_str = msg.get("Date", "")
            message_id = msg.get("Message-ID", f"{folder}_{msg_num}")

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
                raw_content=raw_email.decode("utf-8", errors="ignore"),
                folder=folder,
                metadata={"msg_num": msg_num, "size": len(raw_email)},
            )

            return receipt_email

        except Exception as e:
            logger.error(f"Error fetching email {msg_num}: {e}")
            return None

    def _extract_email_content(self, msg: email.message.Message) -> tuple[str | None, str | None]:
        """Extract HTML and text content from email message."""
        html_content = None
        text_content = None

        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))

                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue

                    if content_type == "text/html":
                        html_payload = part.get_payload(decode=True)
                        if html_payload and isinstance(html_payload, bytes):
                            html_content = html_payload.decode("utf-8", errors="ignore")

                    elif content_type == "text/plain":
                        text_payload = part.get_payload(decode=True)
                        if text_payload and isinstance(text_payload, bytes):
                            text_content = text_payload.decode("utf-8", errors="ignore")

            else:
                # Single part message
                content_type = msg.get_content_type()
                payload = msg.get_payload(decode=True)

                if payload and isinstance(payload, bytes):
                    content = payload.decode("utf-8", errors="ignore")

                    if content_type == "text/html":
                        html_content = content
                    elif content_type == "text/plain":
                        text_content = content

        except Exception as e:
            logger.error(f"Error extracting email content: {e}")

        return html_content, text_content

    def _decode_header(self, header: str) -> str:
        """Decode email header with proper encoding handling."""
        if not header:
            return ""

        try:
            decoded_header = email.header.decode_header(header)
            decoded_parts = []

            for part, encoding in decoded_header:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_parts.append(part.decode(encoding, errors="ignore"))
                    else:
                        decoded_parts.append(part.decode("utf-8", errors="ignore"))
                else:
                    decoded_parts.append(str(part))

            return "".join(decoded_parts)

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
            "@apple.com",
            "@itunes.com",
            "@icloud.com",
            "no_reply@email.apple.com",  # Fixed: Apple uses underscore format
            "do_not_reply@itunes.com",
        ]

        sender_check = any(domain in email_obj.sender.lower() for domain in apple_senders)
        if not sender_check:
            logger.warning(
                f"❌ Sender check failed - Sender: '{email_obj.sender}' | Subject: '{email_obj.subject}'"
            )
            return False

        # Check subject for receipt indicators
        subject_lower = email_obj.subject.lower()
        receipt_indicators = [
            "receipt",
            "your receipt from apple",
            "thank you for your purchase",
            "itunes store",
            "app store",
            "apple store",
        ]

        subject_check = any(indicator in subject_lower for indicator in receipt_indicators)
        if not subject_check:
            logger.warning(f"❌ Subject check failed - Subject: '{email_obj.subject}'")
            return False

        # Check content for purchase indicators
        content_to_check = (email_obj.html_content or "") + (email_obj.text_content or "")
        content_lower = content_to_check.lower()

        # Log content length for debugging
        html_len = len(email_obj.html_content) if email_obj.html_content else 0
        text_len = len(email_obj.text_content) if email_obj.text_content else 0

        content_indicators = [
            "total",
            "order id",
            "document no",
            "purchase",
            "download",
            "subscription",
            "$",
            "£",
            "€",
            "¥",  # Currency symbols
        ]

        content_check = any(indicator in content_lower for indicator in content_indicators)
        if not content_check:
            logger.warning(
                f"❌ Content check failed - No purchase indicators found | "
                f"Subject: '{email_obj.subject}' | HTML: {html_len} chars | Text: {text_len} chars"
            )
            return False

        # Exclude promotional/non-receipt emails
        exclusion_terms = [
            "promotional",
            "marketing",
            "newsletter",
            "survey",
            "feedback",
            "update your",
            "privacy policy",
            "terms of service",
        ]

        exclusion_check = any(term in content_lower for term in exclusion_terms)
        if exclusion_check:
            logger.warning(f"❌ Exclusion check triggered - Subject: '{email_obj.subject}'")
            return False

        logger.info(f"✅ Email passed all checks: '{email_obj.subject}'")
        return True

    def save_emails_to_disk(self, emails: list[AppleReceiptEmail], output_dir: Path) -> dict[str, Any]:
        """
        Save fetched emails to disk for processing.

        Args:
            emails: List of AppleReceiptEmail objects
            output_dir: Directory to save emails

        Returns:
            Dictionary with save statistics
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        stats: dict[str, Any] = {
            "total_emails": len(emails),
            "saved_successfully": 0,
            "save_errors": 0,
            "files_created": [],
        }

        for i, email_obj in enumerate(emails):
            try:
                # Create base filename from email metadata
                safe_subject = re.sub(r"[^\w\-_\.]", "_", email_obj.subject)[:50]
                base_name = f"{email_obj.date.strftime('%Y%m%d_%H%M%S')}_{safe_subject}_{i:03d}"

                # Save HTML content if available
                if email_obj.html_content:
                    html_file = output_dir / f"{base_name}-formatted-simple.html"
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(email_obj.html_content)
                    files_list: list[Any] = stats["files_created"]
                    files_list.append(str(html_file))

                # Save text content if available
                if email_obj.text_content:
                    text_file = output_dir / f"{base_name}.txt"
                    with open(text_file, "w", encoding="utf-8") as f:
                        f.write(email_obj.text_content)
                    files_list = stats["files_created"]
                    files_list.append(str(text_file))

                # Save raw email
                raw_file = output_dir / f"{base_name}.eml"
                with open(raw_file, "w", encoding="utf-8") as f:
                    f.write(email_obj.raw_content or "")
                files_list = stats["files_created"]
                files_list.append(str(raw_file))

                # Save metadata
                metadata_file = output_dir / f"{base_name}_metadata.json"
                metadata = {
                    "message_id": email_obj.message_id,
                    "subject": email_obj.subject,
                    "sender": email_obj.sender,
                    "date": email_obj.date.isoformat(),
                    "folder": email_obj.folder,
                    "metadata": email_obj.metadata,
                }

                write_json(metadata_file, metadata)
                files_list = stats["files_created"]
                files_list.append(str(metadata_file))

                saved_count: int = stats["saved_successfully"]
                stats["saved_successfully"] = saved_count + 1

            except Exception as e:
                # PERF203: try-except in loop necessary for robust file I/O operations
                logger.error(f"Error saving email {i}: {e}")
                error_count: int = stats["save_errors"]
                stats["save_errors"] = error_count + 1

        logger.info(f"Saved {stats['saved_successfully']}/{stats['total_emails']} emails to {output_dir}")
        return stats

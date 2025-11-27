#!/usr/bin/env python3
"""
Integration tests for Apple Email Fetcher.

Tests email save/load workflows without heavy IMAP mocking.
Focuses on file system operations and email processing.
"""

import email
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from finances.apple.email_fetcher import AppleEmailFetcher, AppleReceiptEmail, EmailConfig


@pytest.fixture
def email_config():
    """Create a test email configuration."""
    return EmailConfig(
        imap_server="test.imap.example.com",
        imap_port=993,
        username="test@example.com",
        password="test_password",  # noqa: S106
    )


@pytest.fixture
def sample_email_objects():
    """Create sample AppleReceiptEmail objects for testing."""
    return [
        AppleReceiptEmail(
            message_id="msg001",
            subject="Your receipt from Apple - Procreate",
            sender="no_reply@email.apple.com",
            date=datetime(2024, 8, 15, 10, 30, 0),
            html_content="<html><body><p>Receipt for Procreate $29.99</p></body></html>",
            text_content="Receipt for Procreate $29.99",
            raw_content="From: no_reply@email.apple.com\nSubject: Your receipt from Apple\n\nReceipt content",
            folder="INBOX",
            metadata={"msg_num": "1", "size": 1024},
        ),
        AppleReceiptEmail(
            message_id="msg002",
            subject="Your receipt from Apple - Apple Music",
            sender="do_not_reply@itunes.com",
            date=datetime(2024, 9, 20, 14, 45, 0),
            html_content="<html><body><p>Apple Music subscription $10.98</p></body></html>",
            text_content="Apple Music subscription $10.98",
            raw_content="From: do_not_reply@itunes.com\nSubject: Apple Music\n\nSubscription renewal",
            folder="[Gmail]/All Mail",
            metadata={"msg_num": "2", "size": 2048},
        ),
    ]


@pytest.mark.integration
@pytest.mark.apple
def test_save_emails_complete(email_config, sample_email_objects, temp_dir):
    """Test complete email save workflow with comprehensive validation."""
    from finances.core.json_utils import read_json

    fetcher = AppleEmailFetcher(email_config)

    output_dir = temp_dir / "saved_emails"

    # Save emails
    stats = fetcher.save_emails_to_disk(sample_email_objects, output_dir)

    # Verify statistics
    assert stats["total_emails"] == 2
    assert stats["saved_successfully"] == 2
    assert stats["save_errors"] == 0
    assert len(stats["files_created"]) > 0

    # Verify directory created
    assert output_dir.exists()
    assert output_dir.is_dir()

    # Verify files created
    files = list(output_dir.glob("*"))
    assert len(files) > 0

    # Each email should generate multiple files (html, txt, eml, metadata)
    html_files = sorted(output_dir.glob("*-formatted-simple.html"))
    eml_files = list(output_dir.glob("*.eml"))
    metadata_files = sorted(output_dir.glob("*_metadata.json"))

    assert len(html_files) == 2
    assert len(eml_files) == 2
    assert len(metadata_files) == 2

    # Verify HTML content integrity
    # First HTML file
    with open(html_files[0], encoding="utf-8") as f:
        content = f.read()
    assert "Procreate" in content
    assert "$29.99" in content

    # Second HTML file
    with open(html_files[1], encoding="utf-8") as f:
        content = f.read()
    assert "Apple Music" in content
    assert "$10.98" in content

    # Verify metadata structure and content
    # First metadata file
    metadata1 = read_json(metadata_files[0])
    assert "message_id" in metadata1
    assert "subject" in metadata1
    assert "sender" in metadata1
    assert "date" in metadata1
    assert "folder" in metadata1
    assert "metadata" in metadata1

    assert metadata1["message_id"] == "msg001"
    assert "Procreate" in metadata1["subject"]
    assert metadata1["sender"] == "no_reply@email.apple.com"


@pytest.mark.integration
@pytest.mark.apple
def test_save_emails_creates_directory_if_missing(email_config, sample_email_objects, temp_dir):
    """Test that save operation creates output directory if it doesn't exist."""
    fetcher = AppleEmailFetcher(email_config)

    # Use non-existent nested directory
    output_dir = temp_dir / "nested" / "path" / "to" / "emails"
    assert not output_dir.exists()

    # Save emails
    stats = fetcher.save_emails_to_disk(sample_email_objects, output_dir)

    # Verify directory created
    assert output_dir.exists()
    assert stats["saved_successfully"] == 2


@pytest.mark.integration
@pytest.mark.apple
def test_save_emails_with_special_characters_in_subject(email_config, temp_dir):
    """Test saving emails with special characters in subject."""
    special_email = AppleReceiptEmail(
        message_id="msg_special",
        subject="Your receipt: App Name / Special & Chars! <Test>",
        sender="noreply@apple.com",
        date=datetime(2024, 10, 5, 12, 0, 0),
        html_content="<html><body>Special chars test</body></html>",
        text_content="Special chars test",
        raw_content="Test email",
        folder="INBOX",
    )

    fetcher = AppleEmailFetcher(email_config)
    output_dir = temp_dir / "special_chars"

    stats = fetcher.save_emails_to_disk([special_email], output_dir)

    # Should succeed without errors
    assert stats["saved_successfully"] == 1
    assert stats["save_errors"] == 0

    # Verify files created with sanitized names
    files = list(output_dir.glob("*"))
    assert len(files) > 0


@pytest.mark.integration
@pytest.mark.apple
def test_decode_header_with_various_encodings(email_config):
    """Test email header decoding with various character encodings."""
    fetcher = AppleEmailFetcher(email_config)

    # Test simple ASCII
    result = fetcher._decode_header("Simple Subject")
    assert result == "Simple Subject"

    # Test empty header
    result = fetcher._decode_header("")
    assert result == ""

    # Test None header
    result = fetcher._decode_header(None)
    assert result == ""


@pytest.mark.integration
@pytest.mark.apple
def test_is_apple_receipt_validation(email_config):
    """Test Apple receipt email validation logic."""
    fetcher = AppleEmailFetcher(email_config)

    # Valid Apple receipt
    valid_email = AppleReceiptEmail(
        message_id="valid001",
        subject="Your receipt from Apple",
        sender="no_reply@email.apple.com",
        date=datetime.now(),
        html_content="<html>Order ID: ABC123 Total: $29.99</html>",
        text_content="Order ID: ABC123 Total: $29.99",
    )
    assert fetcher._is_apple_receipt(valid_email) is True

    # Invalid sender
    invalid_sender = AppleReceiptEmail(
        message_id="invalid001",
        subject="Your receipt from Apple",
        sender="fake@example.com",
        date=datetime.now(),
        html_content="<html>Receipt</html>",
    )
    assert fetcher._is_apple_receipt(invalid_sender) is False

    # Invalid subject
    invalid_subject = AppleReceiptEmail(
        message_id="invalid002",
        subject="Promotional email",
        sender="noreply@apple.com",
        date=datetime.now(),
        html_content="<html>Promo</html>",
    )
    assert fetcher._is_apple_receipt(invalid_subject) is False

    # Missing content indicators
    missing_content = AppleReceiptEmail(
        message_id="invalid003",
        subject="Your receipt from Apple",
        sender="noreply@apple.com",
        date=datetime.now(),
        html_content="<html>No financial info</html>",
        text_content="No financial info",
    )
    assert fetcher._is_apple_receipt(missing_content) is False

    # Promotional exclusion
    promo_email = AppleReceiptEmail(
        message_id="promo001",
        subject="Your receipt from Apple",
        sender="noreply@apple.com",
        date=datetime.now(),
        html_content="<html>This is promotional content. Total: $29.99</html>",
    )
    assert fetcher._is_apple_receipt(promo_email) is False

    # Email with privacy policy footer link (should PASS - not an exclusion term)
    privacy_footer_email = AppleReceiptEmail(
        message_id="valid002",
        subject="Your receipt from Apple",
        sender="no_reply@email.apple.com",
        date=datetime.now(),
        html_content='<html>Order ID: XYZ789 Total: $14.99<br/><a href="https://apple.com/legal/privacy/">Privacy Policy</a></html>',
        text_content="Order ID: XYZ789 Total: $14.99",
    )
    assert fetcher._is_apple_receipt(privacy_footer_email) is True

    # Email with marketing in image URL (should PASS - not an exclusion term)
    marketing_url_email = AppleReceiptEmail(
        message_id="valid003",
        subject="Your receipt from Apple",
        sender="no_reply@email.apple.com",
        date=datetime.now(),
        html_content='<html><img src="https://cdn.apple.com/AppIcon-1x_U007emarketing-0-10.png"/> Order ID: ABC456 Total: $9.99</html>',
        text_content="Order ID: ABC456 Total: $9.99",
    )
    assert fetcher._is_apple_receipt(marketing_url_email) is True


@pytest.mark.integration
@pytest.mark.apple
def test_extract_email_content_multipart(email_config):
    """Test extracting content from multipart email messages."""
    fetcher = AppleEmailFetcher(email_config)

    # Create a multipart email message
    msg = email.message.EmailMessage()
    msg["Subject"] = "Test Receipt"
    msg["From"] = "noreply@apple.com"
    msg["Date"] = email.utils.formatdate(localtime=True)

    msg.set_content("Plain text version of receipt")
    msg.add_alternative("<html><body>HTML version of receipt</body></html>", subtype="html")

    # Extract content
    html_content, text_content = fetcher._extract_email_content(msg)

    # Verify both parts extracted
    assert html_content is not None
    assert "HTML version" in html_content
    assert text_content is not None
    assert "Plain text version" in text_content


@pytest.mark.integration
@pytest.mark.apple
def test_extract_email_content_single_part(email_config):
    """Test extracting content from single-part email messages."""
    fetcher = AppleEmailFetcher(email_config)

    # Create a simple text email
    msg = email.message.EmailMessage()
    msg["Subject"] = "Test"
    msg.set_content("Simple text email")

    html_content, text_content = fetcher._extract_email_content(msg)

    # Should have text content
    assert text_content is not None
    assert "Simple text email" in text_content

    # Create a simple HTML email
    html_msg = email.message.EmailMessage()
    html_msg["Subject"] = "Test HTML"
    html_msg.set_content("<html><body>HTML email</body></html>", subtype="html")

    html_content, text_content = fetcher._extract_email_content(html_msg)

    # Should have HTML content
    assert html_content is not None
    assert "HTML email" in html_content


@pytest.mark.integration
@pytest.mark.apple
def test_save_empty_email_list(email_config, temp_dir):
    """Test saving an empty list of emails."""
    fetcher = AppleEmailFetcher(email_config)

    output_dir = temp_dir / "empty_save"

    stats = fetcher.save_emails_to_disk([], output_dir)

    # Should handle gracefully
    assert stats["total_emails"] == 0
    assert stats["saved_successfully"] == 0
    assert stats["save_errors"] == 0
    assert len(stats["files_created"]) == 0

    # Directory should still be created
    assert output_dir.exists()


@pytest.mark.integration
@pytest.mark.apple
def test_list_all_folders(email_config):
    """Test IMAP folder discovery and parsing."""
    fetcher = AppleEmailFetcher(email_config)

    # Mock IMAP connection with folder list response
    mock_connection = MagicMock()
    fetcher.connection = mock_connection

    # Simulate IMAP LIST response with various folder formats
    mock_folders = [
        b'(\\HasNoChildren) "/" "INBOX"',
        b'(\\HasNoChildren) "/" "[Gmail]/All Mail"',
        b'(\\HasChildren) "/" "Archive"',
        b'(\\HasNoChildren \\UnMarked) "." "Follow Up"',
        b'(\\HasNoChildren) "/" "Sent Items"',
        b"invalid_format",  # Should be skipped gracefully
    ]
    mock_connection.list.return_value = ("OK", mock_folders)

    # Execute
    folders = fetcher._list_all_folders()

    # Verify
    assert len(folders) == 5  # Should parse 5 valid folders, skip invalid
    assert "INBOX" in folders
    assert "[Gmail]/All Mail" in folders
    assert "Archive" in folders
    assert "Follow Up" in folders
    assert "Sent Items" in folders


@pytest.mark.integration
@pytest.mark.apple
def test_search_with_deduplication(email_config):
    """Test multi-pattern search deduplicates message IDs."""
    fetcher = AppleEmailFetcher(email_config)

    # Mock IMAP connection
    mock_connection = MagicMock()
    fetcher.connection = mock_connection

    # Simulate search results where some message IDs appear in multiple patterns
    # Message IDs: 1, 2, 3 from first pattern; 2, 3, 4 from second pattern
    # Result should be deduplicated to: 1, 2, 3, 4
    search_results = {
        'SUBJECT "Your receipt from Apple"': b"1 2 3",
        'SUBJECT "Receipt from Apple"': b"2 3 4",
        'FROM "no_reply@email.apple.com"': b"3 4 5",
    }

    def mock_search(_, pattern):
        return ("OK", [search_results.get(pattern, b"")])

    mock_connection.search.side_effect = mock_search
    mock_connection.select.return_value = ("OK", [])

    # Mock fetch to return minimal valid email data
    def mock_fetch(msg_id, _):
        email_content = f"""From: no_reply@email.apple.com
Subject: Your receipt from Apple
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <msg{msg_id}@apple.com>

Receipt for purchase $9.99
Order ID: TEST123
Total: $9.99
"""
        return ("OK", [[None, email_content.encode()]])

    mock_connection.fetch.side_effect = mock_fetch

    # Execute
    receipts = fetcher._search_apple_receipts_in_folder("INBOX")

    # Verify deduplication - should have 5 unique receipts (1, 2, 3, 4, 5)
    # Each message ID appears only once despite being in multiple search results
    assert len(receipts) == 5
    assert len({r.message_id for r in receipts}) == 5


@pytest.mark.integration
@pytest.mark.apple
def test_is_apple_receipt_edge_cases(email_config):
    """Test email validation with edge cases and non-Apple emails."""
    fetcher = AppleEmailFetcher(email_config)

    # Test valid Apple receipt
    valid_receipt = AppleReceiptEmail(
        message_id="msg001",
        subject="Your receipt from Apple",
        sender="no_reply@email.apple.com",
        date=datetime(2024, 1, 1),
        html_content="<p>Total: $9.99</p><p>Order ID: ABC123</p>",
        text_content="Total: $9.99\nOrder ID: ABC123",
    )
    assert fetcher._is_apple_receipt(valid_receipt) is True

    # Test wrong sender domain
    wrong_sender = AppleReceiptEmail(
        message_id="msg002",
        subject="Your receipt from Apple",
        sender="fake@scammer.com",
        date=datetime(2024, 1, 1),
        html_content="<p>Total: $9.99</p>",
        text_content="Total: $9.99",
    )
    assert fetcher._is_apple_receipt(wrong_sender) is False

    # Test non-receipt subject
    wrong_subject = AppleReceiptEmail(
        message_id="msg003",
        subject="Apple News Update",
        sender="no_reply@email.apple.com",
        date=datetime(2024, 1, 1),
        html_content="<p>Check out these articles</p>",
        text_content="Check out these articles",
    )
    assert fetcher._is_apple_receipt(wrong_subject) is False

    # Test missing purchase indicators in content
    no_purchase_content = AppleReceiptEmail(
        message_id="msg004",
        subject="Your receipt from Apple",
        sender="no_reply@email.apple.com",
        date=datetime(2024, 1, 1),
        html_content="<p>Thank you for contacting us</p>",
        text_content="Thank you for contacting us",
    )
    assert fetcher._is_apple_receipt(no_purchase_content) is False

    # Test promotional email (excluded)
    promotional = AppleReceiptEmail(
        message_id="msg005",
        subject="Your receipt from Apple - Special Offer!",
        sender="no_reply@email.apple.com",
        date=datetime(2024, 1, 1),
        html_content="<p>Promotional offer! Total: $9.99</p>",
        text_content="Promotional offer! Total: $9.99",
    )
    assert fetcher._is_apple_receipt(promotional) is False

    # Test alternative valid sender (iTunes)
    itunes_receipt = AppleReceiptEmail(
        message_id="msg006",
        subject="Receipt from Apple - Music subscription",
        sender="do_not_reply@itunes.com",
        date=datetime(2024, 1, 1),
        html_content="<p>Subscription: $10.99</p><p>Total: $10.99</p>",
        text_content="Subscription: $10.99\nTotal: $10.99",
    )
    assert fetcher._is_apple_receipt(itunes_receipt) is True

    # Test email with currency symbols (valid purchase indicator)
    currency_symbols = AppleReceiptEmail(
        message_id="msg007",
        subject="Your receipt from Apple",
        sender="no_reply@email.apple.com",
        date=datetime(2024, 1, 1),
        html_content="<p>Total: €9.99</p><p>Order: TEST</p>",
        text_content="Total: €9.99\nOrder: TEST",
    )
    assert fetcher._is_apple_receipt(currency_symbols) is True

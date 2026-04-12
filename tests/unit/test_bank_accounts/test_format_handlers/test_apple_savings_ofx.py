import pytest

from finances.bank_accounts.format_handlers.apple_savings_ofx import AppleSavingsOfxHandler
from finances.core import FinancialDate, Money


@pytest.fixture
def sample_ofx(tmp_path):
    """Create a temporary Apple Savings OFX file in OFX 1.x SGML format (matches real Apple exports)."""
    ofx_content = (
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        "VERSION:102\n"
        "SECURITY:NONE\n"
        "ENCODING:USASCII\n"
        "CHARSET:1252\n"
        "COMPRESSION:NONE\n"
        "OLDFILEUID:NONE\n"
        "NEWFILEUID:NONE\n"
        "\n"
        "<OFX>"
        "<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS>"
        "<DTSERVER>20241231120000[0:GMT]<LANGUAGE>ENG</SONRS></SIGNONMSGSRSV1>"
        "<BANKMSGSRSV1><STMTTRNRS><TRNUID>0"
        "<STATUS><CODE>0<SEVERITY>INFO</STATUS>"
        "<STMTRS><CURDEF>USD"
        "<BANKACCTFROM><ACCTID>1234567890<ACCTTYPE>SAVINGS</BANKACCTFROM>"
        "<BANKTRANLIST>"
        "<STMTTRN><TRNTYPE>INT<DTPOSTED>20241231120000[0:GMT]"
        "<TRNAMT>1.25<FITID>20241231-1<NAME>Interest Earned</STMTTRN>"
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20241230120000[0:GMT]"
        "<TRNAMT>-500.00<FITID>20241230-1<NAME>Withdrawal to Apple Card</STMTTRN>"
        "</BANKTRANLIST>"
        "<LEDGERBAL><BALAMT>42053.56<DTASOF>20241231120000[0:GMT]</LEDGERBAL>"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    )

    ofx_file = tmp_path / "apple_savings_sample.ofx"
    ofx_file.write_text(ofx_content)
    return ofx_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = AppleSavingsOfxHandler()

    assert handler.format_name == "apple_savings_ofx"
    assert handler.supported_extensions == (".ofx",)


def test_parse_transactions(sample_ofx):
    """Test parsing OFX transactions with NO sign flipping."""
    handler = AppleSavingsOfxHandler()
    result = handler.parse(sample_ofx)

    assert len(result.transactions) == 2

    # First transaction (interest - positive, use as-is)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-31")
    assert tx1.description == "Interest Earned"
    assert tx1.amount == Money.from_cents(125)  # NO sign flipping (already accounting standard)

    # Second transaction (withdrawal - negative, use as-is)
    tx2 = result.transactions[1]
    assert tx2.posted_date == FinancialDate.from_string("2024-12-30")
    assert tx2.description == "Withdrawal to Apple Card"
    assert tx2.amount == Money.from_cents(-50000)  # NO sign flipping


def test_parse_balance(sample_ofx):
    """Test parsing balance data from OFX (ONE balance point, NO available)."""
    handler = AppleSavingsOfxHandler()
    result = handler.parse(sample_ofx)

    assert len(result.balance_points) == 1

    balance = result.balance_points[0]
    assert balance.date == FinancialDate.from_string("2024-12-31")
    assert balance.amount == Money.from_cents(4205356)
    assert balance.available is None  # Savings accounts don't have available balance


def test_parse_statement_date(sample_ofx):
    """Test extracting statement date from OFX."""
    handler = AppleSavingsOfxHandler()
    result = handler.parse(sample_ofx)

    # Statement date should be the balance date
    assert result.statement_date == FinancialDate.from_string("2024-12-31")

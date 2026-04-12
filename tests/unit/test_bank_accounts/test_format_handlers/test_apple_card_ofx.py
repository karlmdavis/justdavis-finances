import pytest

from finances.bank_accounts.format_handlers.apple_card_ofx import AppleCardOfxHandler
from finances.core import FinancialDate, Money


@pytest.fixture
def sample_ofx(tmp_path):
    """Create a temporary Apple Card OFX file in OFX 1.x SGML format (matches real Apple exports)."""
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
        "<CREDITCARDMSGSRSV1><CCSTMTTRNRS><TRNUID>0"
        "<STATUS><CODE>0<SEVERITY>INFO</STATUS>"
        "<CCSTMTRS><CURDEF>USD<CCACCTFROM><ACCTID>1234567890</CCACCTFROM>"
        "<BANKTRANLIST>"
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20241231120000[0:GMT]"
        "<TRNAMT>-94.52<FITID>20241231-1<NAME>AMAZON MKTPL*ZP5WJ4KK2</STMTTRN>"
        "<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20241229120000[0:GMT]"
        "<TRNAMT>150.00<FITID>20241229-1<NAME>PAYMENT - THANK YOU</STMTTRN>"
        "</BANKTRANLIST>"
        "<LEDGERBAL><BALAMT>-182830.90<DTASOF>20241231120000[0:GMT]</LEDGERBAL>"
        "<AVAILBAL><BALAMT>217169.10<DTASOF>20241231120000[0:GMT]</AVAILBAL>"
        "</CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>\n"
    )

    ofx_file = tmp_path / "apple_card_sample.ofx"
    ofx_file.write_text(ofx_content)
    return ofx_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = AppleCardOfxHandler()

    assert handler.format_name == "apple_card_ofx"
    assert handler.supported_extensions == (".ofx",)


def test_parse_transactions(sample_ofx):
    """Test parsing OFX transactions."""
    handler = AppleCardOfxHandler()
    result = handler.parse(sample_ofx)

    assert len(result.transactions) == 2

    # First transaction (debit - already negative in OFX)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-31")
    assert tx1.description == "AMAZON MKTPL*ZP5WJ4KK2"
    assert tx1.amount == Money.from_cents(-9452)  # Use as-is (already accounting standard)

    # Second transaction (credit - positive in OFX)
    tx2 = result.transactions[1]
    assert tx2.posted_date == FinancialDate.from_string("2024-12-29")
    assert tx2.amount == Money.from_cents(15000)  # Use as-is


def test_parse_balance(sample_ofx):
    """Test parsing balance data from OFX."""
    handler = AppleCardOfxHandler()
    result = handler.parse(sample_ofx)

    assert len(result.balance_points) == 1

    balance = result.balance_points[0]
    assert balance.date == FinancialDate.from_string("2024-12-31")
    assert balance.amount == Money.from_cents(-18283090)
    assert balance.available == Money.from_cents(21716910)


def test_parse_statement_date(sample_ofx):
    """Test extracting statement date from OFX."""
    handler = AppleCardOfxHandler()
    result = handler.parse(sample_ofx)

    # Statement date should be the balance date
    assert result.statement_date == FinancialDate.from_string("2024-12-31")

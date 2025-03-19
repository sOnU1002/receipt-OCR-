import pytest
from unittest.mock import patch, MagicMock
from app.utils.ocr_processor import OCRProcessor
from datetime import datetime

@pytest.fixture
def mock_processor():
    processor = OCRProcessor('/path/to/test.pdf')
    processor.extracted_text = """
    STORE NAME
    123 Main Street
    City, State 12345
    Date: 12/31/2022
    
    Item 1         10.99
    Item 2 x 2     21.98
    
    Subtotal       32.97
    Tax            2.64
    TOTAL          35.61
    
    CREDIT CARD
    """
    return processor

def test_extract_merchant_name(mock_processor):
    merchant = mock_processor.extract_merchant_name()
    assert merchant == "STORE NAME"

def test_extract_date(mock_processor):
    with patch('dateutil.parser.parse') as mock_parse:
        mock_parse.return_value = datetime(2022, 12, 31)
        date = mock_processor.extract_date()
        assert date == datetime(2022, 12, 31)

def test_extract_total_amount(mock_processor):
    amount = mock_processor.extract_total_amount()
    assert amount == 35.61

def test_extract_payment_method(mock_processor):
    payment = mock_processor.extract_payment_method()
    assert payment == "CREDIT"

def test_process_receipt(mock_processor):
    with patch.multiple(mock_processor, 
                       extract_merchant_name=MagicMock(return_value="STORE NAME"),
                       extract_date=MagicMock(return_value=datetime(2022, 12, 31)),
                       extract_total_amount=MagicMock(return_value=35.61),
                       extract_currency=MagicMock(return_value="USD"),
                       extract_payment_method=MagicMock(return_value="CREDIT"),
                       extract_tax_amount=MagicMock(return_value=2.64),
                       extract_items=MagicMock(return_value=[
                           {'item_name': 'Item 1', 'quantity': 1.0, 'unit_price': 10.99, 'total_price': 10.99},
                           {'item_name': 'Item 2', 'quantity': 2.0, 'unit_price': 10.99, 'total_price': 21.98}
                       ])):
        result = mock_processor.process_receipt()
        assert result['merchant_name'] == "STORE NAME"
        assert result['purchased_at'] == datetime(2022, 12, 31)
        assert result['total_amount'] == 35.61
        assert result['currency'] == "USD"
        assert result['payment_method'] == "CREDIT"
        assert result['tax_amount'] == 2.64
        assert len(result['items']) == 2
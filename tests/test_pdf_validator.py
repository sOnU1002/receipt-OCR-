import os
import pytest
from app.utils.pdf_validator import PDFValidator

def test_valid_pdf(tmp_path):
    # This test would need a valid PDF file
    # For a complete test, you would need to create a mock PDF file
    pass

def test_invalid_pdf_not_exists():
    validator = PDFValidator('/path/to/nonexistent/file.pdf')
    is_valid, reason = validator.is_valid_pdf()
    assert is_valid is False
    assert "does not exist" in reason

def test_invalid_file_extension(tmp_path):
    # Create a text file with .txt extension
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is not a PDF")
    
    validator = PDFValidator(str(test_file))
    is_valid, reason = validator.is_valid_pdf()
    assert is_valid is False
    assert "not a PDF" in reason
import os
import logging
from PyPDF2 import PdfReader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFValidator:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
    
    def is_valid_pdf(self):
        """
        Check if the file is a valid PDF
        
        Returns:
            tuple: (is_valid, reason)
            - is_valid (bool): True if valid, False otherwise
            - reason (str): Reason for invalidity if not valid, else None
        """
        # Check if file exists
        if not os.path.exists(self.pdf_path):
            return False, "File does not exist"
        
        # Check file extension
        _, extension = os.path.splitext(self.pdf_path)
        if extension.lower() != '.pdf':
            return False, "File is not a PDF"
        
        # Try to open and read the PDF
        try:
            with open(self.pdf_path, 'rb') as file:
                pdf = PdfReader(file)
                
                # Check if PDF has at least one page
                if len(pdf.pages) < 1:
                    return False, "PDF has no pages"
                
                # PDF is valid
                return True, None
                
        except Exception as e:
            logger.error(f"Error validating PDF: {str(e)}")
            return False, f"Invalid PDF format: {str(e)}"
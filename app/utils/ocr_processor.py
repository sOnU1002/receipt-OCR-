import os
import re
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from datetime import datetime
import dateutil.parser
import logging
import json
from fuzzywuzzy import fuzz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class OCRProcessor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.text = ""
        self.lines = []
        self.common_merchants = [
            "walmart", "target", "costco", "kroger", "amazon", "starbucks", 
            "mcdonald's", "subway", "cvs", "walgreens", "cheesecake factory",
            "burger king", "pizza hut", "taco bell", "home depot", "lowes",
            "best buy", "staples", "office depot", "whole foods", "trader joe's"
        ]
        self.payment_methods = [
            "credit", "debit", "cash", "visa", "mastercard", "amex", "american express",
            "discover", "check", "apple pay", "google pay", "paypal"
        ]
        self.currency_symbols = ["$", "€", "£", "¥"]
        
    def preprocess_image(self, image):
        """Apply image preprocessing to improve OCR quality"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
        
        # Apply slight blur to reduce noise
        blur = cv2.GaussianBlur(thresh, (3, 3), 0)
        
        # Apply dilation to make text more prominent
        kernel = np.ones((1, 1), np.uint8)
        dilated = cv2.dilate(blur, kernel, iterations=1)
        
        return dilated
    
    def extract_text(self):
        """Convert PDF to images and extract text using Tesseract OCR"""
        logger.info(f"Processing PDF: {self.pdf_path}")
        try:
            # Convert PDF to images
            images = convert_from_path(self.pdf_path)
            
            all_text = []
            for i, image in enumerate(images):
                # Convert PIL image to numpy array for OpenCV
                open_cv_image = np.array(image)
                open_cv_image = open_cv_image[:, :, ::-1].copy()  # Convert RGB to BGR
                
                # Preprocess the image
                processed_image = self.preprocess_image(open_cv_image)
                
                # Extract text using Tesseract with optimized configuration
                custom_config = r'--oem 3 --psm 6 -l eng -c preserve_interword_spaces=1'
                page_text = pytesseract.image_to_string(processed_image, config=custom_config)
                all_text.append(page_text)
                
                # Debug: save processed image for inspection
                # cv2.imwrite(f"processed_page_{i}.png", processed_image)
            
            self.text = "\n".join(all_text)
            self.lines = [line.strip() for line in self.text.split('\n') if line.strip()]
            logger.info(f"Successfully extracted {len(self.lines)} lines of text")
            return True
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return False
    
    def clean_text(self, text):
        """Clean and normalize text"""
        # Replace common OCR errors
        text = text.replace('$', '$').replace('S', 's')
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def extract_amount(self, text):
        """Extract monetary amount from text"""
        # Look for currency symbol followed by digits with optional decimal point
        amount_patterns = [
            r'[$€£¥]\s*(\d+[.,]\d{2})',  # $XX.XX
            r'(\d+[.,]\d{2})\s*[$€£¥]',  # XX.XX$
            r'total:?\s*[$€£¥]?\s*(\d+[.,]\d{2})',  # Total: $XX.XX
            r'amount:?\s*[$€£¥]?\s*(\d+[.,]\d{2})',  # Amount: $XX.XX
            r'[$€£¥]?\s*(\d+[.,]\d{2})',  # Just look for dollar amounts as fallback
        ]
        
        for pattern in amount_patterns:
            matches = re.search(pattern, text.lower())
            if matches:
                amount = matches.group(1).replace(',', '.')
                try:
                    return float(amount)
                except ValueError:
                    continue
        return None
    
    def extract_merchant(self):
        """Extract merchant name from receipt"""
        potential_merchants = []
        
        # Check first 10 lines for merchant name (often at the top)
        top_lines = self.lines[:min(10, len(self.lines))]
        for line in top_lines:
            line = line.lower()
            # Check against known merchants
            for merchant in self.common_merchants:
                if merchant in line or fuzz.partial_ratio(merchant, line) > 80:
                    return merchant.title()
            
            # Look for patterns like "Welcome to" or store indicators
            if any(x in line for x in ["welcome to", "store", "restaurant", "cafe", "shop"]):
                # Extract potential name (not very long, usually 1-3 words)
                words = line.split()
                if 1 < len(words) < 6:
                    potential_merchants.append(" ".join(words))
        
        # If found potential merchants, return the shortest one (often more accurate)
        if potential_merchants:
            return min(potential_merchants, key=len).title()
            
        # Fallback: look for consistent text in the first 3 lines that might be a name
        if len(self.lines) >= 2:
            return self.lines[0].strip().title()
            
        return "Unknown Merchant"
    
    def extract_date(self):
        """Extract date from receipt text and return a datetime object"""
        # Common date patterns
        date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # MM/DD/YYYY, DD/MM/YYYY
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}',  # DD Mon YYYY
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}',  # Mon DD, YYYY
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\s+\d{2,4}',   # Mon DD YYYY
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',  # YYYY-MM-DD
            r'date:?\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # Date: MM/DD/YYYY
            r'date:?\s+(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',  # Date: DD Mon YYYY
        ]
        
        for line in self.lines:
            line = line.lower()
            for pattern in date_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    date_str = match.group(0)
                    # Try to parse the date
                    try:
                        parsed_date = dateutil.parser.parse(date_str)
                        return parsed_date  # Return datetime object directly
                    except (ValueError, dateutil.parser.ParserError):
                        continue
        
        # If no date found, return today's date
        return datetime.now()  # Return datetime object
    
    def extract_total_amount(self):
        """Extract total amount from receipt"""
        # Look for lines containing 'total', 'amount', 'sum', or 'balance'
        amount_keywords = ['total', 'amount', 'sum', 'balance', 'due', 'charge']
        
        # First try to find explicit total lines
        for line in self.lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in amount_keywords):
                amount = self.extract_amount(line)
                if amount:
                    return amount
        
        # If no explicit total, look for the largest amount in the last part of the receipt
        last_lines = self.lines[-min(15, len(self.lines)):]
        amounts = []
        for line in last_lines:
            amount = self.extract_amount(line)
            if amount:
                amounts.append(amount)
        
        if amounts:
            return max(amounts)
        
        return None
    
    def extract_tax_amount(self):
        """Extract tax amount from receipt"""
        tax_keywords = ['tax', 'vat', 'gst', 'hst', 'sales tax']
        
        for line in self.lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in tax_keywords):
                amount = self.extract_amount(line)
                if amount:
                    return amount
        
        return None
    
    def extract_payment_method(self):
        """Extract payment method information"""
        for line in self.lines:
            line_lower = line.lower()
            for method in self.payment_methods:
                if method in line_lower:
                    return method.title()
        
        # Look for patterns like "Paid by", "Payment:", etc.
        payment_patterns = [
            r'paid\s+by\s+([a-zA-Z\s]+)',
            r'payment:?\s+([a-zA-Z\s]+)',
            r'payment\s+method:?\s+([a-zA-Z\s]+)'
        ]
        
        for line in self.lines:
            line_lower = line.lower()
            for pattern in payment_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    method = match.group(1).strip()
                    if len(method) > 2:
                        return method.title()
        
        return "Unknown"
    
    def extract_currency(self):
        """Extract currency information (default to USD)"""
        currency_patterns = {
            'USD': r'\$|\bUSD\b|\bUS\s*dollar\b',
            'EUR': r'€|\bEUR\b|\bEuro\b',
            'GBP': r'£|\bGBP\b|\bPound\b',
            'JPY': r'¥|\bJPY\b|\bYen\b',
        }
        
        for line in self.lines:
            line_lower = line.lower()
            for currency, pattern in currency_patterns.items():
                if re.search(pattern, line):
                    return currency
        
        # Default to USD if no currency found
        return "USD"
    
    def extract_items(self):
        """Extract individual items from receipt"""
        items = []
        item_pattern = re.compile(r'(\d+)\s+(.+?)\s+([\d.,]+)')
        
        # Find where the items section likely begins and ends
        item_section_start = -1
        item_section_end = len(self.lines)
        item_section_markers = ['item', 'qty', 'description', 'price', 'amount']
        end_section_markers = ['subtotal', 'total', 'tax', 'balance', 'due', 'payment']
        
        # Find the start of the items section
        for i, line in enumerate(self.lines):
            line_lower = line.lower()
            # Check if this looks like a header row for items
            if any(marker in line_lower for marker in item_section_markers):
                item_section_start = i + 1
                break
        
        # If we couldn't find an explicit header, make an educated guess
        if item_section_start == -1:
            # Skip the first few lines (usually store info/header)
            item_section_start = min(5, len(self.lines) - 1)
            
        # Find the end of the items section
        for i in range(item_section_start, len(self.lines)):
            line_lower = self.lines[i].lower()
            if any(marker in line_lower for marker in end_section_markers):
                item_section_end = i
                break
        
        # Look for lines with price patterns in the identified section
        price_pattern = r'\$?\s*(\d+\.\d{2})'
        quantity_pattern = r'(\d+)\s*(?:x|@|ea)'
        
        i = item_section_start
        while i < item_section_end:
            line = self.lines[i].strip()
            line_lower = line.lower()
            
            # Skip dividers, empty lines, or lines that look like section headers
            if not line or all(c in '-=*' for c in line) or any(marker in line_lower for marker in item_section_markers):
                i += 1
                continue
            
            # Check if line contains a price
            price_match = re.search(price_pattern, line)
            
            if price_match:
                # This looks like an item line
                try:
                    price = float(price_match.group(1))
                    
                    # Extract item description (everything before the price)
                    description_end = price_match.start()
                    description = line[:description_end].strip()
                    
                    # If description is too short, it might be just a quantity or code
                    # Try to combine with previous line
                    if len(description) < 3 and i > item_section_start:
                        description = self.lines[i-1].strip() + " " + description
                    
                    # Extract quantity if present
                    quantity = 1
                    qty_match = re.search(quantity_pattern, line)
                    if qty_match:
                        try:
                            quantity = int(qty_match.group(1))
                        except ValueError:
                            pass
                    
                    # If description still looks valid
                    if len(description) >= 2:
                        items.append({
                            'description': description,
                            'quantity': quantity,
                            'price': price,
                            'amount': price * quantity
                        })
                except ValueError:
                    pass  # Skip if price conversion fails
            
            # Check next line
            i += 1
        
        # If we didn't find many items, try a different approach
        if len(items) < 2:
            # Look for price patterns throughout the receipt
            for i in range(item_section_start, item_section_end):
                line = self.lines[i].strip()
                price_match = re.search(price_pattern, line)
                if price_match:
                    try:
                        price = float(price_match.group(1))
                        # Skip very high prices which might be totals
                        if price < 100:
                            # Find description (text before the price)
                            desc_end = price_match.start()
                            description = line[:desc_end].strip()
                            
                            # If description is empty or too short, use previous line
                            if len(description) < 2 and i > 0:
                                description = self.lines[i-1].strip()
                            
                            if len(description) >= 2:
                                items.append({
                                    'description': description,
                                    'quantity': 1,
                                    'price': price,
                                    'amount': price
                                })
                    except ValueError:
                        pass  # Skip if conversion fails
        
        # Try one more approach for special receipt formats
        if len(items) < 2:
            # Look for patterns where item and price are on separate lines
            for i in range(item_section_start, item_section_end - 1):
                current_line = self.lines[i].strip()
                next_line = self.lines[i + 1].strip()
                
                # Check if current line has no price but next line does
                if not re.search(price_pattern, current_line) and re.search(price_pattern, next_line):
                    price_match = re.search(price_pattern, next_line)
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                            # Skip lines that might be totals
                            if price < 100 and len(current_line) >= 2:
                                items.append({
                                    'description': current_line,
                                    'quantity': 1,
                                    'price': price,
                                    'amount': price
                                })
                        except ValueError:
                            pass
        
        # Filter out likely non-items (too short descriptions or missing amounts)
        filtered_items = []
        for item in items:
            if len(item['description']) > 2 and item.get('amount') is not None:
                # Clean up description - remove common prefixes like item numbers
                item['description'] = re.sub(r'^\d+\s+', '', item['description'])
                filtered_items.append(item)
        
        return filtered_items
    
    def process(self):
        """Process the receipt and extract all relevant information"""
        if not self.extract_text():
            logger.error("Failed to extract text from receipt")
            return None
        
        # Extract receipt information
        merchant_name = self.extract_merchant()
        date = self.extract_date()  # This is now a datetime object
        total_amount = self.extract_total_amount()
        tax_amount = self.extract_tax_amount()
        payment_method = self.extract_payment_method()
        currency = self.extract_currency()
        items = self.extract_items()
        
        # Ensure date is definitely a datetime object
        if isinstance(date, str):
            logger.warning("Date was returned as a string, converting to datetime")
            try:
                date = dateutil.parser.parse(date)
            except:
                date = datetime.now()
        
        receipt_data = {
            'merchant_name': merchant_name,
            'purchased_at': date,  # This should be a datetime object
            'date': date,  # Keep this for compatibility
            'total_amount': total_amount,
            'tax_amount': tax_amount,
            'payment_method': payment_method,
            'currency': currency,
            'items': items,
            'text': self.text
        }
        
        logger.info(f"Successfully processed receipt from {merchant_name}, dated {date}")
        logger.info(f"Found {len(items)} items totaling {total_amount} {currency}")
        
        return receipt_data
        
    def process_receipt(self):
        """Alias for process() method for backward compatibility"""
        return self.process()
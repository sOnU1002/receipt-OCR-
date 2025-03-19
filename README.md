# Receipt OCR Project

A comprehensive OCR (Optical Character Recognition) application for digitizing and processing receipts. This application extracts key information such as merchant names, dates, items, and prices from receipt images or PDFs.

## Features
- **PDF & Image Processing**: Upload and process receipts in PDF or image formats.
- **Text Extraction**: Extract text from receipts using advanced OCR technology.
- **Information Extraction**: Automatically identify and extract:
  - Merchant name
  - Purchase date
  - Total amount
  - Tax amount
  - Payment method
  - Line items with quantities and prices
- **Data Validation**: Verify receipt authenticity and validity.
- **Data Storage**: Store processed receipt data in a database.
- **API Interface**: RESTful API for integration with other systems.

## Setup

### Prerequisites
- Python 3.8+
- Tesseract OCR engine
- Poppler for PDF processing
- Virtual environment (recommended)

### Installation

#### Clone the repository
```bash
git clone <repository-url>
cd receipt-ocr-project
```

#### Create and activate a virtual environment
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On MacOS/Linux
source venv/bin/activate
```

#### Install dependencies
```bash
pip install -r requirements.txt
```

#### Install Tesseract OCR
- **Windows**: Download and install from [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki).
- **MacOS**: 
  ```bash
  brew install tesseract
  ```
- **Linux**:
  ```bash
  sudo apt-get install tesseract-ocr
  ```

#### Install Poppler (Required for PDF Processing)
- **Windows**: Download and install [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases) and add it to your system PATH.
- **MacOS**:
  ```bash
  brew install poppler
  ```
- **Linux**:
  ```bash
  sudo apt-get install poppler-utils
  ```

#### Initialize the database
```bash
flask db init
flask db migrate
flask db upgrade
```

## Usage

#### Running the Application
```bash
python run.py
```
The application will start on [http://localhost:5000](http://localhost:5000).

### API Endpoints
- **Upload Receipt**: `POST /api/upload`
  - Accepts multipart/form-data with a file field.
  - Returns receipt ID for further processing.
- **Validate Receipt**: `POST /api/validate/<receipt_id>`
  - Validates the uploaded receipt.
  - Returns validation status.
- **Process Receipt**: `POST /api/process/<receipt_id>`
  - Extracts information from a validated receipt.
  - Returns extracted data.
- **Get Receipt**: `GET /api/receipts/<receipt_id>`
  - Returns stored receipt data.
- **List Receipts**: `GET /api/receipts`
  - Returns a list of all processed receipts.

### Test the Application
To test the application, go to:
[http://localhost:5000/api/upload](http://localhost:5000/api/upload)

## Project Structure
```bash
receipt-ocr-project/
├── app/
│   ├── __init__.py
│   ├── models/
│   │   └── receipt_models.py
│   ├── routes/
│   │   └── receipt_routes.py
│   ├── utils/
│   │   ├── ocr_processor.py
│   │   └── pdf_validator.py
│   └── static/
│       └── uploads/
├── tests/
│   └── test_ocr_processor.py
├── run.py
├── config.py
└── requirements.txt
``` 

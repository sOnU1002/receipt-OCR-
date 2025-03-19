from flask import Blueprint, request, jsonify, current_app, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import uuid
from flask import Blueprint, request, jsonify, current_app, send_from_directory, redirect, url_for, render_template_string
from app import db
from app.models.receipt_models import ReceiptFile, Receipt, ReceiptItem
from app.utils.pdf_validator import PDFValidator
from app.utils.ocr_processor import OCRProcessor
import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

receipt_bp = Blueprint('receipts', __name__, url_prefix='/api')

# Add a route for the API root
@receipt_bp.route('/', methods=['GET'])
def api_root():
    return jsonify({
        'message': 'Receipt OCR API',
        'version': '1.0',
        'endpoints': {
            'upload': '/api/upload [POST] - Upload a receipt',
            'validate': '/api/validate/<receipt_id> [POST] - Validate a receipt',
            'process': '/api/process/<receipt_id> [POST] - Process and extract information from a receipt',
            'receipts': '/api/receipts [GET] - Get all processed receipts',
            'receipt': '/api/receipts/<receipt_id> [GET] - Get details of a specific receipt',
            'receipt_files': '/api/receipt-files [GET] - Get all receipt files',
            'download': '/api/download/<receipt_id> [GET] - Download a receipt file'
        }
    })

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@receipt_bp.route('/upload', methods=['POST'])
def upload_receipt():
    # Check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    # If user does not select file, browser also submits an empty part without filename
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # Create unique filename to avoid duplicates
        original_filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4()}_{original_filename}"
        
        # Create year-based directory if it doesn't exist
        year = datetime.now().strftime('%Y')
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], year)
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        absolute_path = os.path.abspath(file_path)
        
        # Save the file
        file.save(file_path)
        
        # Check if this file was already uploaded (by checking the original filename)
        existing_receipt = ReceiptFile.query.filter_by(file_name=original_filename).first()
        
        if existing_receipt:
            # Update existing receipt
            existing_receipt.file_path = absolute_path
            existing_receipt.is_valid = None
            existing_receipt.invalid_reason = None
            existing_receipt.is_processed = False
            existing_receipt.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'message': 'Receipt updated successfully', 'receipt_id': existing_receipt.id}), 200
        else:
            # Create new receipt file entry
            receipt_file = ReceiptFile(
                file_name=original_filename,
                file_path=absolute_path
            )
            db.session.add(receipt_file)
            db.session.commit()
            
            return jsonify({'message': 'Receipt uploaded successfully', 'receipt_id': receipt_file.id}), 201
    
    return jsonify({'error': 'File type not allowed'}), 400

@receipt_bp.route('/validate/<int:receipt_id>', methods=['POST'])
def validate_receipt(receipt_id):
    receipt_file = ReceiptFile.query.get_or_404(receipt_id)
    
    # Validate PDF
    validator = PDFValidator(receipt_file.file_path)
    is_valid, reason = validator.is_valid_pdf()
    
    # Update receipt file
    receipt_file.is_valid = is_valid
    receipt_file.invalid_reason = reason
    receipt_file.updated_at = datetime.utcnow()
    db.session.commit()
    
    if is_valid:
        return jsonify({'message': 'Receipt is valid', 'receipt_id': receipt_id}), 200
    else:
        return jsonify({'message': 'Receipt is invalid', 'reason': reason, 'receipt_id': receipt_id}), 200

@receipt_bp.route('/process/<int:receipt_id>', methods=['POST'])
def process_receipt(receipt_id):
    receipt_file = ReceiptFile.query.get_or_404(receipt_id)
    
    # Check if receipt is valid
    if receipt_file.is_valid is None:
        return jsonify({'error': 'Receipt has not been validated yet'}), 400
    if not receipt_file.is_valid:
        return jsonify({'error': 'Cannot process invalid receipt'}), 400
    
    try:
        # Process the receipt using OCR
        processor = OCRProcessor(receipt_file.file_path)
        result = processor.process_receipt()
        
        # Check if a receipt already exists for this file
        existing_receipt = Receipt.query.filter_by(receipt_file_id=receipt_id).first()
        
        if existing_receipt:
            # Update existing receipt
            existing_receipt.merchant_name = result['merchant_name']
            existing_receipt.purchased_at = result['purchased_at']
            existing_receipt.total_amount = result['total_amount']
            existing_receipt.currency = result['currency']
            existing_receipt.payment_method = result['payment_method']
            existing_receipt.tax_amount = result.get('tax_amount')
            existing_receipt.updated_at = datetime.utcnow()
            
            # Delete existing receipt items
            ReceiptItem.query.filter_by(receipt_id=existing_receipt.id).delete()
            
            # Create new receipt items
            for item_data in result.get('items', []):
                item = ReceiptItem(

                    receipt_id=new_receipt.id,
                    item_name=item_data.get('description', ''),  # Change "name" to "item_name"
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data.get('price', 0.0),  # Change "price" to "unit_price"
                    total_price=item_data.get('amount', 0.0)  # Change "amount" to "total_price"
                )
                db.session.add(item)
                
            db.session.commit()
            return jsonify({'message': 'Receipt updated successfully', 'receipt_id': existing_receipt.id}), 200
        else:
            # Create new receipt
            new_receipt = Receipt(
                receipt_file_id=receipt_id,
                merchant_name=result['merchant_name'],
                purchased_at=result['purchased_at'],
                total_amount=result['total_amount'],
                currency=result['currency'],
                payment_method=result['payment_method'],
                tax_amount=result.get('tax_amount')
            )
            db.session.add(new_receipt)
            db.session.flush()  # Generate ID for new receipt
            
            # Create receipt items
            for item_data in result.get('items', []):
                item = ReceiptItem(
                    receipt_id=new_receipt.id,
                    item_name=item_data.get('description', ''),
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data.get('price', 0.0),
                    total_price=item_data.get('amount', 0.0)
                )
                db.session.add(item)
                
            db.session.commit()
            return jsonify({'message': 'Receipt processed successfully', 'receipt_id': new_receipt.id}), 201
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing receipt: {str(e)}")
        return jsonify({'error': f'Error processing receipt: {str(e)}'}), 500

@receipt_bp.route('/receipts', methods=['GET'])
def get_receipts():
    receipts = Receipt.query.all()
    return jsonify({'receipts': [receipt.to_dict() for receipt in receipts]}), 200

@receipt_bp.route('/receipts/<int:receipt_id>', methods=['GET'])
def get_receipt(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    return jsonify({'receipt': receipt.to_dict()}), 200

@receipt_bp.route('/receipt-files', methods=['GET'])
def get_receipt_files():
    receipt_files = ReceiptFile.query.all()
    return jsonify({'receipt_files': [rf.to_dict() for rf in receipt_files]}), 200

@receipt_bp.route('/download/<int:receipt_id>', methods=['GET'])
def download_receipt(receipt_id):
    receipt_file = ReceiptFile.query.get_or_404(receipt_id)
    directory, filename = os.path.split(receipt_file.file_path)
    return send_from_directory(directory, filename, as_attachment=True)


@receipt_bp.route('/upload-dashboard', methods=['GET'])
def upload_dashboard():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Receipt OCR Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1000px;
                margin: 0 auto;
                padding: 20px;
            }
            h1, h2, h3 {
                color: #333;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            .btn {
                background-color: #4CAF50;
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                margin-right: 10px;
            }
            .btn-secondary {
                background-color: #2196F3;
            }
            .btn-danger {
                background-color: #f44336;
            }
            .btn:hover {
                opacity: 0.8;
            }
            .card {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 15px;
                margin-bottom: 20px;
                background-color: #f9f9f9;
            }
            .response {
                margin-top: 10px;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f5f5f5;
                white-space: pre-wrap;
                max-height: 300px;
                overflow-y: auto;
            }
            .tabs {
                display: flex;
                border-bottom: 1px solid #ddd;
                margin-bottom: 20px;
            }
            .tab {
                padding: 10px 15px;
                cursor: pointer;
                margin-right: 5px;
            }
            .tab.active {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-bottom: none;
            }
            .tab-content {
                display: none;
            }
            .tab-content.active {
                display: block;
            }
            .receipt-item {
                margin-bottom: 10px;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                cursor: pointer;
            }
            .receipt-item:hover {
                background-color: #f0f0f0;
            }
            .receipt-details {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }
            .hidden {
                display: none;
            }
        </style>
    </head>
    <body>
        <h1>Receipt OCR Dashboard</h1>
        
        <div class="tabs">
            <div class="tab active" data-tab="upload">Upload</div>
            <div class="tab" data-tab="receipts">Receipts</div>
            <div class="tab" data-tab="details">Receipt Details</div>
        </div>
        
        <div class="tab-content active" id="upload">
            <div class="card">
                <h2>Upload New Receipt</h2>
                <form id="uploadForm">
                    <div class="form-group">
                        <label for="file">Select Receipt PDF:</label>
                        <input type="file" id="file" name="file" accept=".pdf" required>
                    </div>
                    <button type="submit" class="btn">Upload Receipt</button>
                </form>
                <div id="uploadResponse" class="response hidden"></div>
            </div>
            
            <div class="card hidden" id="processCard">
                <h2>Process Receipt</h2>
                <p>Receipt ID: <span id="receiptId"></span></p>
                <button id="validateBtn" class="btn btn-secondary">Validate</button>
                <button id="processBtn" class="btn btn-secondary">Process</button>
                <div id="processResponse" class="response hidden"></div>
            </div>
        </div>
        
        <div class="tab-content" id="receipts">
            <div class="card">
                <h2>All Receipts</h2>
                <button id="loadReceiptsBtn" class="btn">Load Receipts</button>
                <div id="receiptsList"></div>
                <div id="receiptsResponse" class="response hidden"></div>
            </div>
        </div>
        
        <div class="tab-content" id="details">
            <div class="card">
                <h2>Receipt Details</h2>
                <p>Select a receipt from the Receipts tab to view details</p>
                <div id="receiptDetails" class="receipt-details hidden"></div>
                <div id="detailsResponse" class="response hidden"></div>
            </div>
        </div>
        
        <script>
            // Tab functionality
            document.querySelectorAll('.tab').forEach(tab => {
                tab.addEventListener('click', () => {
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    
                    tab.classList.add('active');
                    document.getElementById(tab.dataset.tab).classList.add('active');
                });
            });
            
            // Form submission
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData();
                const fileInput = document.getElementById('file');
                
                if (fileInput.files.length === 0) {
                    alert('Please select a file');
                    return;
                }
                
                formData.append('file', fileInput.files[0]);
                
                try {
                    const response = await fetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    const uploadResponse = document.getElementById('uploadResponse');
                    uploadResponse.textContent = JSON.stringify(result, null, 2);
                    uploadResponse.classList.remove('hidden');
                    
                    if (result.receipt_id) {
                        document.getElementById('receiptId').textContent = result.receipt_id;
                        document.getElementById('processCard').classList.remove('hidden');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    document.getElementById('uploadResponse').textContent = 'Error: ' + error.message;
                }
            });
            
            // Validate button
            document.getElementById('validateBtn').addEventListener('click', async () => {
                const receiptId = document.getElementById('receiptId').textContent;
                
                try {
                    const response = await fetch(`/api/validate/${receiptId}`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    const processResponse = document.getElementById('processResponse');
                    processResponse.textContent = JSON.stringify(result, null, 2);
                    processResponse.classList.remove('hidden');
                } catch (error) {
                    console.error('Error:', error);
                    document.getElementById('processResponse').textContent = 'Error: ' + error.message;
                    document.getElementById('processResponse').classList.remove('hidden');
                }
            });
            
            // Process button
            document.getElementById('processBtn').addEventListener('click', async () => {
                const receiptId = document.getElementById('receiptId').textContent;
                
                try {
                    const response = await fetch(`/api/process/${receiptId}`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    const processResponse = document.getElementById('processResponse');
                    processResponse.textContent = JSON.stringify(result, null, 2);
                    processResponse.classList.remove('hidden');
                    
                    // Switch to receipts tab after processing
                    document.querySelector('.tab[data-tab="receipts"]').click();
                    document.getElementById('loadReceiptsBtn').click();
                } catch (error) {
                    console.error('Error:', error);
                    document.getElementById('processResponse').textContent = 'Error: ' + error.message;
                    document.getElementById('processResponse').classList.remove('hidden');
                }
            });
            
            // Load receipts button
            document.getElementById('loadReceiptsBtn').addEventListener('click', async () => {
                try {
                    const response = await fetch('/api/receipts');
                    const result = await response.json();
                    
                    const receiptsList = document.getElementById('receiptsList');
                    receiptsList.innerHTML = '';
                    
                    if (result.receipts && result.receipts.length > 0) {
                        result.receipts.forEach(receipt => {
                            const item = document.createElement('div');
                            item.className = 'receipt-item';
                            item.setAttribute('data-id', receipt.id);
                            item.textContent = `Receipt #${receipt.id}: ${receipt.merchant_name || 'Unknown'} - ${receipt.date || 'No date'} - ${receipt.total_amount || 'No amount'}`;
                            
                            item.addEventListener('click', () => {
                                loadReceiptDetails(receipt.id);
                                document.querySelector('.tab[data-tab="details"]').click();
                            });
                            
                            receiptsList.appendChild(item);
                        });
                    } else {
                        receiptsList.innerHTML = '<p>No receipts found. Upload and process some receipts first.</p>';
                    }
                    
                    const receiptsResponse = document.getElementById('receiptsResponse');
                    receiptsResponse.textContent = JSON.stringify(result, null, 2);
                    receiptsResponse.classList.remove('hidden');
                } catch (error) {
                    console.error('Error:', error);
                    document.getElementById('receiptsResponse').textContent = 'Error: ' + error.message;
                    document.getElementById('receiptsResponse').classList.remove('hidden');
                }
            });
            
            // Load receipt details
            async function loadReceiptDetails(receiptId) {
                try {
                    const response = await fetch(`/api/receipts/${receiptId}`);
                    const result = await response.json();
                    
                    const detailsElement = document.getElementById('receiptDetails');
                    detailsElement.innerHTML = '';
                    detailsElement.classList.remove('hidden');
                    
                    if (result.receipt) {
                        const receipt = result.receipt;
                        
                        // Create details HTML
                        let detailsHtml = `
                            <div>
                                <h3>Receipt Information</h3>
                                <p><strong>ID:</strong> ${receipt.id}</p>
                                <p><strong>Merchant:</strong> ${receipt.merchant_name || 'Unknown'}</p>
                                <p><strong>Date:</strong> ${receipt.date || 'Unknown'}</p>
                                <p><strong>Total Amount:</strong> ${receipt.total_amount || 'Unknown'} ${receipt.currency || ''}</p>
                                <p><strong>Payment Method:</strong> ${receipt.payment_method || 'Unknown'}</p>
                                <p><strong>Tax Amount:</strong> ${receipt.tax_amount || 'Unknown'}</p>
                                <a href="/api/download/${receipt.receipt_file_id}" target="_blank" class="btn">Download PDF</a>
                            </div>
                            <div>
                                <h3>Items</h3>
                        `;
                        
                        if (receipt.items && receipt.items.length > 0) {
                            detailsHtml += '<ul>';
                            receipt.items.forEach(item => {
                                detailsHtml += `<li>${item.description || 'Unknown item'} - ${item.amount || 'No price'}</li>`;
                            });
                            detailsHtml += '</ul>';
                        } else {
                            detailsHtml += '<p>No items found</p>';
                        }
                        
                        detailsHtml += '</div>';
                        detailsElement.innerHTML = detailsHtml;
                    } else {
                        detailsElement.innerHTML = '<p>Receipt details not found</p>';
                    }
                    
                    const detailsResponse = document.getElementById('detailsResponse');
                    detailsResponse.textContent = JSON.stringify(result, null, 2);
                    detailsResponse.classList.remove('hidden');
                } catch (error) {
                    console.error('Error:', error);
                    document.getElementById('detailsResponse').textContent = 'Error: ' + error.message;
                    document.getElementById('detailsResponse').classList.remove('hidden');
                }
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

from app import db
from datetime import datetime

class ReceiptFile(db.Model):
    __tablename__ = 'receipt_file'
    
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    is_valid = db.Column(db.Boolean, default=None)
    invalid_reason = db.Column(db.String(512))
    is_processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    receipt = db.relationship('Receipt', backref='receipt_file', uselist=False, cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'is_valid': self.is_valid,
            'invalid_reason': self.invalid_reason,
            'is_processed': self.is_processed,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Receipt(db.Model):
    __tablename__ = 'receipt'
    
    id = db.Column(db.Integer, primary_key=True)
    receipt_file_id = db.Column(db.Integer, db.ForeignKey('receipt_file.id'), nullable=False)
    purchased_at = db.Column(db.DateTime)
    merchant_name = db.Column(db.String(255))
    total_amount = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional fields as needed
    currency = db.Column(db.String(10))
    payment_method = db.Column(db.String(50))
    tax_amount = db.Column(db.Float)
    items = db.relationship('ReceiptItem', backref='receipt', cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'file_name': self.receipt_file.file_name if self.receipt_file else None,
            'file_path': self.receipt_file.file_path if self.receipt_file else None,
            'purchased_at': self.purchased_at.isoformat() if self.purchased_at else None,
            'merchant_name': self.merchant_name,
            'total_amount': self.total_amount,
            'currency': self.currency,
            'payment_method': self.payment_method,
            'tax_amount': self.tax_amount,
            'items': [item.to_dict() for item in self.items],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class ReceiptItem(db.Model):
    __tablename__ = 'receipt_item'
    
    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipt.id'), nullable=False)
    item_name = db.Column(db.String(255))
    quantity = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float)
    total_price = db.Column(db.Float)
    
    def to_dict(self):
        return {
            'id': self.id,
            'item_name': self.item_name,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total_price': self.total_price
        }
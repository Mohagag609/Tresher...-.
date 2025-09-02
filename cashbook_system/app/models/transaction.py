from datetime import datetime
from decimal import Decimal
import uuid
from app import db

class CashTransaction(db.Model):
    __tablename__ = 'cash_transactions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Voucher info
    voucher_no = db.Column(db.String(30), unique=True, nullable=False, index=True)
    
    # Transaction details
    cashbox_id = db.Column(db.Integer, db.ForeignKey('cashboxes.id'), nullable=False)
    txn_type = db.Column(db.String(20), nullable=False)
    # receipt, payment, transfer_out, transfer_in
    
    status = db.Column(db.String(10), nullable=False, default='draft')
    # draft, approved, void
    
    date = db.Column(db.Date, nullable=False, default=datetime.today)
    
    # Financial details
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    currency = db.Column(db.String(3), default='EGP', nullable=False)
    exchange_rate = db.Column(db.Numeric(12, 6), default=Decimal('1.000000'))
    amount_base = db.Column(db.Numeric(15, 2))  # Amount in base currency
    
    # Related entities
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    partner_id = db.Column(db.Integer, db.ForeignKey('partners.id'))
    
    # Project/Cost center (optional)
    project_code = db.Column(db.String(50))
    cost_center = db.Column(db.String(50))
    
    # Description
    description = db.Column(db.Text)
    reference_no = db.Column(db.String(100))  # External reference (invoice no, etc.)
    
    # For transfers - linked transaction
    linked_txn_id = db.Column(db.String(36), db.ForeignKey('cash_transactions.id'))
    
    # User tracking
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    voided_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    voided_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Void reason
    void_reason = db.Column(db.Text)
    
    # Relationships
    linked_txn = db.relationship('CashTransaction', remote_side=[id], uselist=False)
    attachments = db.relationship('TransactionAttachment', backref='transaction', 
                                 lazy='dynamic', cascade='all, delete-orphan')
    voided_by = db.relationship('User', foreign_keys=[voided_by_id])
    
    def generate_voucher_no(self):
        """Generate unique voucher number"""
        from sqlalchemy import func
        
        year = datetime.now().year
        prefix = f"{self.cashbox.code}-{year}"
        
        # Get last voucher number for this prefix
        last_voucher = CashTransaction.query.filter(
            CashTransaction.voucher_no.like(f'{prefix}-%')
        ).order_by(CashTransaction.voucher_no.desc()).first()
        
        if last_voucher:
            last_seq = int(last_voucher.voucher_no.split('-')[-1])
            seq = last_seq + 1
        else:
            seq = 1
        
        self.voucher_no = f"{prefix}-{seq:06d}"
    
    def approve(self, user):
        """Approve transaction"""
        if self.status != 'draft':
            raise ValueError('يمكن اعتماد المسودات فقط')
        
        # Check cashbox balance for payments
        if self.txn_type == 'payment':
            if self.cashbox.current_balance < self.amount:
                raise ValueError('الرصيد غير كافي للصرف')
        
        self.status = 'approved'
        self.approved_by_id = user.id
        self.approved_at = datetime.utcnow()
        
    def void(self, user, reason):
        """Void transaction"""
        if self.status != 'approved':
            raise ValueError('يمكن إلغاء المعاملات المعتمدة فقط')
        
        self.status = 'void'
        self.voided_by_id = user.id
        self.voided_at = datetime.utcnow()
        self.void_reason = reason
        
        # Void linked transfer transaction if exists
        if self.linked_txn and self.linked_txn.status == 'approved':
            self.linked_txn.void(user, f'إلغاء تلقائي - مرتبط بالسند {self.voucher_no}')
    
    @staticmethod
    def create_transfer(from_box, to_box, amount, user, description="", date=None):
        """Create a transfer between two cashboxes"""
        from app import db
        
        if from_box.current_balance < amount:
            raise ValueError('الرصيد غير كافي للتحويل')
        
        # Create outgoing transaction
        out_txn = CashTransaction(
            cashbox_id=from_box.id,
            txn_type='transfer_out',
            status='draft',
            date=date or datetime.today(),
            amount=amount,
            currency=from_box.currency,
            description=f"تحويل إلى {to_box.name}. {description}",
            created_by_id=user.id
        )
        out_txn.generate_voucher_no()
        
        # Create incoming transaction
        in_txn = CashTransaction(
            cashbox_id=to_box.id,
            txn_type='transfer_in',
            status='draft',
            date=date or datetime.today(),
            amount=amount,
            currency=to_box.currency,
            description=f"تحويل من {from_box.name}. {description}",
            created_by_id=user.id
        )
        in_txn.generate_voucher_no()
        
        # Link transactions
        db.session.add(out_txn)
        db.session.add(in_txn)
        db.session.flush()
        
        out_txn.linked_txn_id = in_txn.id
        in_txn.linked_txn_id = out_txn.id
        
        return out_txn, in_txn
    
    def __repr__(self):
        return f'<Transaction {self.voucher_no} - {self.txn_type} - {self.amount}>'


class TransactionAttachment(db.Model):
    __tablename__ = 'transaction_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(36), db.ForeignKey('cash_transactions.id'), nullable=False)
    
    # File info
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)  # in bytes
    
    # Description
    description = db.Column(db.String(500))
    
    # Upload info
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    uploaded_by = db.relationship('User', backref='uploaded_attachments')
    
    def __repr__(self):
        return f'<Attachment {self.filename}>'
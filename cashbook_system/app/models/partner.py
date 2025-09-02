from datetime import datetime
from app import db

class Partner(db.Model):
    __tablename__ = 'partners'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, index=True)
    name = db.Column(db.String(150), nullable=False)
    name_ar = db.Column(db.String(150))
    
    # Type
    partner_type = db.Column(db.String(20), nullable=False, default='other')
    # customer, supplier, employee, other
    
    # Contact info
    phone = db.Column(db.String(30))
    mobile = db.Column(db.String(30))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    
    # Financial info
    tax_number = db.Column(db.String(50))
    commercial_register = db.Column(db.String(50))
    
    # Bank info
    bank_name = db.Column(db.String(100))
    bank_account = db.Column(db.String(50))
    bank_branch = db.Column(db.String(100))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Notes
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('CashTransaction', backref='partner', lazy='dynamic')
    
    @property
    def total_receipts(self):
        """Total receipts from this partner"""
        from app.models import CashTransaction
        from sqlalchemy import func
        
        return CashTransaction.query.filter_by(
            partner_id=self.id,
            txn_type='receipt',
            status='approved'
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or 0
    
    @property
    def total_payments(self):
        """Total payments to this partner"""
        from app.models import CashTransaction
        from sqlalchemy import func
        
        return CashTransaction.query.filter_by(
            partner_id=self.id,
            txn_type='payment',
            status='approved'
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or 0
    
    @property
    def net_balance(self):
        """Net balance with partner (positive = we owe, negative = they owe)"""
        return self.total_payments - self.total_receipts
    
    def __repr__(self):
        return f'<Partner {self.code} - {self.name}>'
from datetime import datetime
from decimal import Decimal
from app import db

class CashBox(db.Model):
    __tablename__ = 'cashboxes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100))
    description = db.Column(db.Text)
    
    # Financial info
    currency = db.Column(db.String(3), default='EGP', nullable=False)
    opening_balance = db.Column(db.Numeric(15, 2), default=Decimal('0.00'), nullable=False)
    
    # Type and status
    box_type = db.Column(db.String(20), default='main')  # main, branch, petty
    is_active = db.Column(db.Boolean, default=True)
    
    # Branch info (if applicable)
    branch_name = db.Column(db.String(100))
    branch_code = db.Column(db.String(20))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('CashTransaction', backref='cashbox', lazy='dynamic',
                                  foreign_keys='CashTransaction.cashbox_id')
    period_closes = db.relationship('PeriodClose', backref='cashbox', lazy='dynamic')
    
    @property
    def current_balance(self):
        """Calculate current balance: opening + receipts - payments + net transfers"""
        from app.models import CashTransaction
        from sqlalchemy import func
        
        # Get approved transactions only
        approved_txns = CashTransaction.query.filter_by(
            cashbox_id=self.id,
            status='approved'
        )
        
        # Calculate inflows (receipts + transfer_in)
        inflows = approved_txns.filter(
            CashTransaction.txn_type.in_(['receipt', 'transfer_in'])
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
        
        # Calculate outflows (payments + transfer_out)
        outflows = approved_txns.filter(
            CashTransaction.txn_type.in_(['payment', 'transfer_out'])
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
        
        return self.opening_balance + inflows - outflows
    
    @property
    def today_balance_change(self):
        """Get today's balance change"""
        from app.models import CashTransaction
        from sqlalchemy import func
        from datetime import date
        
        today_txns = CashTransaction.query.filter_by(
            cashbox_id=self.id,
            status='approved'
        ).filter(
            func.date(CashTransaction.date) == date.today()
        )
        
        inflows = today_txns.filter(
            CashTransaction.txn_type.in_(['receipt', 'transfer_in'])
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
        
        outflows = today_txns.filter(
            CashTransaction.txn_type.in_(['payment', 'transfer_out'])
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
        
        return inflows - outflows
    
    def __repr__(self):
        return f'<CashBox {self.code} - {self.name}>'


class PeriodClose(db.Model):
    __tablename__ = 'period_closes'
    
    id = db.Column(db.Integer, primary_key=True)
    cashbox_id = db.Column(db.Integer, db.ForeignKey('cashboxes.id'), nullable=False)
    
    # Period info
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    period_type = db.Column(db.String(10), default='monthly')  # monthly, yearly
    
    # Balances at close
    opening_balance = db.Column(db.Numeric(15, 2), nullable=False)
    closing_balance = db.Column(db.Numeric(15, 2), nullable=False)
    total_receipts = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    total_payments = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    total_transfers_in = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    total_transfers_out = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    
    # Close info
    closed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    closed_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    # Ensure unique period per cashbox
    __table_args__ = (
        db.UniqueConstraint('cashbox_id', 'month', 'year', name='_cashbox_period_uc'),
    )
    
    closed_by = db.relationship('User', backref='period_closes')
    
    def __repr__(self):
        return f'<PeriodClose {self.cashbox_id} - {self.month}/{self.year}>'
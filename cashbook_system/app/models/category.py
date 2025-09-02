from datetime import datetime
from app import db

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    name_ar = db.Column(db.String(120))
    
    # Type
    category_type = db.Column(db.String(20), nullable=False)
    # income, expense, transfer
    
    # Hierarchy
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    
    # Display
    icon = db.Column(db.String(50))  # For UI icons
    color = db.Column(db.String(7))  # Hex color for UI
    display_order = db.Column(db.Integer, default=0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Budget (optional)
    monthly_budget = db.Column(db.Numeric(15, 2))
    yearly_budget = db.Column(db.Numeric(15, 2))
    
    # Description
    description = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    parent = db.relationship('Category', remote_side=[id], backref='children')
    transactions = db.relationship('CashTransaction', backref='category', lazy='dynamic')
    
    @property
    def full_path(self):
        """Get full category path (Parent > Child)"""
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    @property
    def total_amount(self):
        """Total amount for this category"""
        from app.models import CashTransaction
        from sqlalchemy import func
        
        return CashTransaction.query.filter_by(
            category_id=self.id,
            status='approved'
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or 0
    
    @property
    def current_month_amount(self):
        """Current month amount for this category"""
        from app.models import CashTransaction
        from sqlalchemy import func, extract
        from datetime import datetime
        
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        return CashTransaction.query.filter_by(
            category_id=self.id,
            status='approved'
        ).filter(
            extract('month', CashTransaction.date) == current_month,
            extract('year', CashTransaction.date) == current_year
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or 0
    
    def __repr__(self):
        return f'<Category {self.code} - {self.name}>'
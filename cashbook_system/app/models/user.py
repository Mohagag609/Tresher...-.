from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    name_ar = db.Column(db.String(50))
    description = db.Column(db.String(200))
    
    # Permissions
    can_create_draft = db.Column(db.Boolean, default=False)
    can_approve = db.Column(db.Boolean, default=False)
    can_void = db.Column(db.Boolean, default=False)
    can_manage_cashbox = db.Column(db.Boolean, default=False)
    can_manage_users = db.Column(db.Boolean, default=False)
    can_view_reports = db.Column(db.Boolean, default=False)
    can_export = db.Column(db.Boolean, default=False)
    can_close_period = db.Column(db.Boolean, default=False)
    
    users = db.relationship('User', backref='role', lazy='dynamic')
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100))
    full_name_ar = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_superuser = db.Column(db.Boolean, default=False)
    
    # Role
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    created_transactions = db.relationship('CashTransaction', 
                                          foreign_keys='CashTransaction.created_by_id',
                                          backref='creator', lazy='dynamic')
    approved_transactions = db.relationship('CashTransaction',
                                           foreign_keys='CashTransaction.approved_by_id',
                                           backref='approver', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission):
        if self.is_superuser:
            return True
        if not self.role:
            return False
        return getattr(self.role, permission, False)
    
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
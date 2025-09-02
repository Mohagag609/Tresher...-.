from datetime import datetime
from app import db

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User info
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    username = db.Column(db.String(80))  # Store username in case user is deleted
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    # Action info
    action = db.Column(db.String(50), nullable=False)
    # login, logout, create, update, delete, approve, void, transfer, export, etc.
    
    model_name = db.Column(db.String(50))  # e.g., 'CashTransaction', 'CashBox'
    record_id = db.Column(db.String(50))  # ID of the affected record
    
    # Changes
    old_values = db.Column(db.JSON)  # JSON of old values
    new_values = db.Column(db.JSON)  # JSON of new values
    
    # Description
    description = db.Column(db.Text)
    
    # Status
    status = db.Column(db.String(20), default='success')  # success, failed, warning
    error_message = db.Column(db.Text)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    @staticmethod
    def log_action(user, action, model_name=None, record_id=None, 
                   old_values=None, new_values=None, description=None,
                   ip_address=None, user_agent=None, status='success', error_message=None):
        """Helper method to create audit log entry"""
        log = AuditLog(
            user_id=user.id if user else None,
            username=user.username if user else 'system',
            action=action,
            model_name=model_name,
            record_id=str(record_id) if record_id else None,
            old_values=old_values,
            new_values=new_values,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )
        db.session.add(log)
        return log
    
    def __repr__(self):
        return f'<AuditLog {self.action} by {self.username} at {self.created_at}>'
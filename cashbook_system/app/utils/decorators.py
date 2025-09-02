from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def permission_required(permission):
    """Decorator to check if user has specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('يجب تسجيل الدخول أولاً', 'warning')
                return redirect(url_for('auth.login'))
            
            if not current_user.has_permission(permission):
                flash('ليس لديك الصلاحية للقيام بهذا الإجراء', 'danger')
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator to check if user is admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_superuser:
            flash('هذه الصفحة للمسؤولين فقط', 'danger')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function
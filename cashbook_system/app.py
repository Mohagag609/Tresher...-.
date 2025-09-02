#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
نظام إدارة الخزينة الاحترافي
Cash Management System
بناءً على المواصفات المطلوبة بالضبط
"""

import os
import sqlite3
import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from flask import Flask, render_template_string, request, redirect, session, jsonify, flash, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'cashbook-professional-system-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create necessary directories
os.makedirs('instance', exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== DATABASE SCHEMA ====================
def init_database():
    """Initialize database with exact schema as requested"""
    conn = sqlite3.connect('instance/cashbook.db')
    c = conn.cursor()
    
    # Enable foreign keys
    c.execute("PRAGMA foreign_keys = ON")
    
    # Users table with Django-like structure
    c.execute('''CREATE TABLE IF NOT EXISTS auth_user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(150) UNIQUE NOT NULL,
        password VARCHAR(128) NOT NULL,
        email VARCHAR(254),
        first_name VARCHAR(150),
        last_name VARCHAR(150),
        is_active BOOLEAN DEFAULT 1,
        is_staff BOOLEAN DEFAULT 0,
        is_superuser BOOLEAN DEFAULT 0,
        date_joined DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Groups for permissions
    c.execute('''CREATE TABLE IF NOT EXISTS auth_group (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(150) UNIQUE NOT NULL
    )''')
    
    # User groups relationship
    c.execute('''CREATE TABLE IF NOT EXISTS auth_user_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES auth_user(id),
        FOREIGN KEY (group_id) REFERENCES auth_group(id),
        UNIQUE(user_id, group_id)
    )''')
    
    # CashBox model - exactly as specified
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_cashbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code VARCHAR(10) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        currency VARCHAR(3) DEFAULT 'EGP',
        opening_balance DECIMAL(12,2) DEFAULT 0.00,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Partner model - exactly as specified
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_partner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(150) NOT NULL,
        kind VARCHAR(10) DEFAULT 'other' CHECK(kind IN ('customer', 'supplier', 'other')),
        phone VARCHAR(30),
        email VARCHAR(254),
        address TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Category model - exactly as specified
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_category (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(120) NOT NULL,
        kind VARCHAR(10) NOT NULL CHECK(kind IN ('income', 'expense', 'transfer')),
        parent_id INTEGER,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES cashbook_category(id) ON DELETE SET NULL
    )''')
    
    # CashTransaction model - exactly as specified
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_cashtransaction (
        id VARCHAR(36) PRIMARY KEY,
        cashbox_id INTEGER NOT NULL,
        txn_type VARCHAR(20) NOT NULL CHECK(txn_type IN ('receipt', 'payment', 'transfer_out', 'transfer_in')),
        status VARCHAR(10) DEFAULT 'draft' CHECK(status IN ('draft', 'approved', 'void')),
        date DATE NOT NULL,
        category_id INTEGER,
        partner_id INTEGER,
        description TEXT,
        amount DECIMAL(12,2) NOT NULL,
        currency VARCHAR(3) DEFAULT 'EGP',
        rate_to_base DECIMAL(12,6) DEFAULT 1.000000,
        voucher_no VARCHAR(30) UNIQUE,
        created_by_id INTEGER NOT NULL,
        approved_by_id INTEGER,
        linked_txn_id VARCHAR(36),
        attachment VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashbook_cashbox(id) ON DELETE RESTRICT,
        FOREIGN KEY (category_id) REFERENCES cashbook_category(id) ON DELETE SET NULL,
        FOREIGN KEY (partner_id) REFERENCES cashbook_partner(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by_id) REFERENCES auth_user(id) ON DELETE RESTRICT,
        FOREIGN KEY (approved_by_id) REFERENCES auth_user(id) ON DELETE SET NULL,
        FOREIGN KEY (linked_txn_id) REFERENCES cashbook_cashtransaction(id) ON DELETE SET NULL
    )''')
    
    # PeriodClose model - exactly as specified
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_periodclose (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cashbox_id INTEGER NOT NULL,
        month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
        year INTEGER NOT NULL,
        closed_by_id INTEGER NOT NULL,
        closed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashbook_cashbox(id) ON DELETE RESTRICT,
        FOREIGN KEY (closed_by_id) REFERENCES auth_user(id) ON DELETE RESTRICT,
        UNIQUE(cashbox_id, month, year)
    )''')
    
    # Audit log table
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_auditlog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action VARCHAR(100) NOT NULL,
        model_name VARCHAR(100),
        object_id VARCHAR(100),
        changes TEXT,
        ip_address VARCHAR(45),
        user_agent TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES auth_user(id)
    )''')
    
    # Create indexes for better performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_cashbox ON cashbook_cashtransaction(cashbox_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON cashbook_cashtransaction(date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_status ON cashbook_cashtransaction(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_voucher ON cashbook_cashtransaction(voucher_no)")
    
    # Check if initial data exists
    c.execute("SELECT COUNT(*) FROM auth_user")
    if c.fetchone()[0] == 0:
        # Create groups
        groups = [
            ('Admin',),
            ('Approver',),
            ('Cashier',),
            ('Auditor',)
        ]
        c.executemany("INSERT INTO auth_group (name) VALUES (?)", groups)
        
        # Create users with exact roles as specified
        users = [
            ('admin', generate_password_hash('admin123'), 'admin@cashbook.com', 'System', 'Admin', 1, 1, 1),
            ('approver', generate_password_hash('approver123'), 'approver@cashbook.com', 'Transaction', 'Approver', 1, 1, 0),
            ('cashier', generate_password_hash('cashier123'), 'cashier@cashbook.com', 'Cash', 'Cashier', 1, 0, 0),
            ('auditor', generate_password_hash('auditor123'), 'auditor@cashbook.com', 'System', 'Auditor', 1, 0, 0)
        ]
        c.executemany("""INSERT INTO auth_user 
                        (username, password, email, first_name, last_name, is_active, is_staff, is_superuser) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", users)
        
        # Assign users to groups
        user_groups = [
            (1, 1),  # admin -> Admin group
            (2, 2),  # approver -> Approver group
            (3, 3),  # cashier -> Cashier group
            (4, 4),  # auditor -> Auditor group
        ]
        c.executemany("INSERT INTO auth_user_groups (user_id, group_id) VALUES (?, ?)", user_groups)
        
        # Create default CashBoxes as specified
        cashboxes = [
            ('MAIN', 'الخزنة الرئيسية', 'EGP', 50000.00, 1),
            ('PETTY', 'العهدة النثرية', 'EGP', 5000.00, 1),
            ('BANK', 'الحساب البنكي', 'EGP', 100000.00, 1),
            ('BRANCH1', 'خزنة الفرع الأول', 'EGP', 20000.00, 1),
            ('BRANCH2', 'خزنة الفرع الثاني', 'EGP', 15000.00, 1)
        ]
        c.executemany("""INSERT INTO cashbook_cashbox 
                        (code, name, currency, opening_balance, is_active) 
                        VALUES (?, ?, ?, ?, ?)""", cashboxes)
        
        # Create default Categories as specified
        categories = [
            ('مبيعات نقدية', 'income'),
            ('مبيعات آجلة', 'income'),
            ('خدمات استشارية', 'income'),
            ('إيرادات أخرى', 'income'),
            ('رواتب وأجور', 'expense'),
            ('إيجار المكتب', 'expense'),
            ('مصروفات إدارية', 'expense'),
            ('مشتريات', 'expense'),
            ('فواتير كهرباء ومياه', 'expense'),
            ('مصروفات صيانة', 'expense'),
            ('تحويلات داخلية', 'transfer')
        ]
        c.executemany("INSERT INTO cashbook_category (name, kind) VALUES (?, ?)", categories)
        
        # Create default Partners as specified
        partners = [
            ('عميل نقدي', 'customer', '01000000000', 'cash@customer.com', 'نقدي'),
            ('شركة الأمل للتجارة', 'customer', '01234567890', 'amal@company.com', 'القاهرة - مصر الجديدة'),
            ('مؤسسة النور', 'customer', '01098765432', 'nour@foundation.org', 'الإسكندرية'),
            ('شركة التوريدات المتحدة', 'supplier', '01111111111', 'united@supplies.com', 'القاهرة - وسط البلد'),
            ('مورد قطع الغيار', 'supplier', '01222222222', 'parts@supplier.com', 'الجيزة'),
            ('شركة الكهرباء', 'supplier', '19999', None, 'مصر'),
            ('شركة المياه', 'supplier', '125', None, 'مصر'),
            ('أحمد محمد - موظف', 'other', '01555555555', 'ahmed@employee.com', 'القاهرة')
        ]
        c.executemany("""INSERT INTO cashbook_partner 
                        (name, kind, phone, email, address) 
                        VALUES (?, ?, ?, ?, ?)""", partners)
    
    conn.commit()
    conn.close()

# Initialize database
init_database()

# ==================== HELPER FUNCTIONS ====================
def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect('instance/cashbook.db')
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def login_required(f):
    """Decorator for routes that require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    """Decorator for routes that require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            # Check user permission based on group
            conn = get_db()
            c = conn.cursor()
            c.execute("""SELECT g.name FROM auth_group g
                        JOIN auth_user_groups ug ON g.id = ug.group_id
                        WHERE ug.user_id = ?""", (session['user_id'],))
            groups = [row['name'] for row in c.fetchall()]
            conn.close()
            
            # Permission mapping
            permissions = {
                'Admin': ['all'],
                'Approver': ['view', 'create', 'approve', 'void'],
                'Cashier': ['view', 'create'],
                'Auditor': ['view', 'reports']
            }
            
            allowed = False
            for group in groups:
                if group == 'Admin' or permission in permissions.get(group, []):
                    allowed = True
                    break
            
            if not allowed:
                flash('ليس لديك صلاحية للوصول لهذه الصفحة', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_audit(action, model_name=None, object_id=None, changes=None):
    """Log audit trail"""
    if 'user_id' not in session:
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO cashbook_auditlog 
                (user_id, action, model_name, object_id, changes, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (session['user_id'], action, model_name, object_id, 
               str(changes) if changes else None,
               request.remote_addr, request.user_agent.string))
    conn.commit()
    conn.close()

def generate_voucher_no(cashbox_id, txn_type):
    """Generate voucher number exactly as specified in the model"""
    conn = get_db()
    c = conn.cursor()
    
    # Get cashbox code
    c.execute("SELECT code FROM cashbook_cashbox WHERE id = ?", (cashbox_id,))
    cashbox = c.fetchone()
    if not cashbox:
        conn.close()
        return None
    
    year = datetime.now().year
    prefix = f"{cashbox['code']}-{year}"
    
    # Get last voucher number for this prefix
    c.execute("""SELECT voucher_no FROM cashbook_cashtransaction 
                WHERE voucher_no LIKE ? 
                ORDER BY voucher_no DESC LIMIT 1""", (f"{prefix}-%",))
    last = c.fetchone()
    
    if last:
        # Extract sequence number
        seq = int(last['voucher_no'].split('-')[-1]) + 1
    else:
        seq = 1
    
    conn.close()
    return f"{prefix}-{seq:06d}"

def get_cashbox_balance(cashbox_id):
    """Calculate balance exactly as specified in the model"""
    conn = get_db()
    c = conn.cursor()
    
    # Get opening balance
    c.execute("SELECT opening_balance FROM cashbook_cashbox WHERE id = ?", (cashbox_id,))
    result = c.fetchone()
    if not result:
        conn.close()
        return Decimal('0.00')
    
    opening_balance = Decimal(str(result['opening_balance']))
    
    # Calculate approved transactions
    c.execute("""SELECT 
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as in_sum,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as out_sum
                 FROM cashbook_cashtransaction 
                 WHERE cashbox_id = ? AND status = 'approved'""", (cashbox_id,))
    result = c.fetchone()
    
    in_sum = Decimal(str(result['in_sum'] or 0))
    out_sum = Decimal(str(result['out_sum'] or 0))
    
    conn.close()
    return opening_balance + in_sum - out_sum

def transfer_between_cashboxes(from_box_id, to_box_id, amount, user_id, description=""):
    """Create transfer transaction exactly as specified in the model"""
    conn = get_db()
    c = conn.cursor()
    
    try:
        # Start transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Get transfer category
        c.execute("SELECT id FROM cashbook_category WHERE kind = 'transfer' LIMIT 1")
        category = c.fetchone()
        category_id = category['id'] if category else None
        
        # Create transfer out transaction
        out_id = str(uuid.uuid4())
        out_voucher = generate_voucher_no(from_box_id, 'transfer_out')
        
        c.execute("""INSERT INTO cashbook_cashtransaction 
                    (id, cashbox_id, txn_type, status, date, category_id, 
                     description, amount, voucher_no, created_by_id, approved_by_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (out_id, from_box_id, 'transfer_out', 'approved', 
                   date.today(), category_id, description, amount,
                   out_voucher, user_id, user_id))
        
        # Create transfer in transaction
        in_id = str(uuid.uuid4())
        in_voucher = generate_voucher_no(to_box_id, 'transfer_in')
        
        # Get from_box name for description
        c.execute("SELECT name FROM cashbook_cashbox WHERE id = ?", (from_box_id,))
        from_box = c.fetchone()
        in_description = f"Transfer from {from_box['name']}. {description}"
        
        c.execute("""INSERT INTO cashbook_cashtransaction 
                    (id, cashbox_id, txn_type, status, date, category_id, 
                     description, amount, voucher_no, created_by_id, approved_by_id, linked_txn_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (in_id, to_box_id, 'transfer_in', 'approved', 
                   date.today(), category_id, in_description, amount,
                   in_voucher, user_id, user_id, out_id))
        
        # Update linked_txn_id for out transaction
        c.execute("UPDATE cashbook_cashtransaction SET linked_txn_id = ? WHERE id = ?",
                  (in_id, out_id))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Transfer error: {e}")
        return False
    finally:
        conn.close()

# ==================== TEMPLATES ====================
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}نظام إدارة الخزينة{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f8f9fa;
        }
        .navbar-brand {
            font-weight: bold;
            font-size: 1.5rem;
        }
        .sidebar {
            min-height: calc(100vh - 56px);
            background: linear-gradient(180deg, #343a40 0%, #495057 100%);
        }
        .sidebar .nav-link {
            color: rgba(255,255,255,0.8);
            padding: 1rem;
            transition: all 0.3s;
        }
        .sidebar .nav-link:hover {
            color: white;
            background-color: rgba(255,255,255,0.1);
        }
        .sidebar .nav-link.active {
            color: white;
            background-color: #007bff;
        }
        .card {
            border: none;
            box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075);
            margin-bottom: 1.5rem;
        }
        .stat-card {
            border-left: 4px solid;
            transition: transform 0.3s;
        }
        .stat-card:hover {
            transform: translateY(-5px);
        }
        .stat-card.primary { border-left-color: #007bff; }
        .stat-card.success { border-left-color: #28a745; }
        .stat-card.warning { border-left-color: #ffc107; }
        .stat-card.danger { border-left-color: #dc3545; }
        .table-responsive {
            background: white;
            border-radius: 0.25rem;
            padding: 1rem;
        }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Navbar -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="{{ url_for('dashboard') }}">
                <i class="fas fa-cash-register"></i> نظام إدارة الخزينة
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    {% if session.user_id %}
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="userDropdown" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-user"></i> {{ session.username }}
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="#">الملف الشخصي</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="{{ url_for('logout') }}">تسجيل الخروج</a></li>
                        </ul>
                    </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    {% if session.user_id %}
    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar -->
            <nav class="col-md-2 d-md-block sidebar">
                <div class="position-sticky pt-3">
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link {% if request.endpoint == 'dashboard' %}active{% endif %}" href="{{ url_for('dashboard') }}">
                                <i class="fas fa-tachometer-alt"></i> لوحة التحكم
                            </a>
                        </li>
                        
                        <li class="nav-item">
                            <a class="nav-link {% if 'transaction' in request.endpoint %}active{% endif %}" href="{{ url_for('transaction_list') }}">
                                <i class="fas fa-exchange-alt"></i> المعاملات
                            </a>
                        </li>
                        
                        <li class="nav-item">
                            <a class="nav-link {% if 'cashbox' in request.endpoint %}active{% endif %}" href="{{ url_for('cashbox_list') }}">
                                <i class="fas fa-box"></i> الخزائن
                            </a>
                        </li>
                        
                        <li class="nav-item">
                            <a class="nav-link {% if 'partner' in request.endpoint %}active{% endif %}" href="{{ url_for('partner_list') }}">
                                <i class="fas fa-users"></i> الشركاء
                            </a>
                        </li>
                        
                        <li class="nav-item">
                            <a class="nav-link {% if 'category' in request.endpoint %}active{% endif %}" href="{{ url_for('category_list') }}">
                                <i class="fas fa-tags"></i> التصنيفات
                            </a>
                        </li>
                        
                        <li class="nav-item">
                            <a class="nav-link {% if 'report' in request.endpoint %}active{% endif %}" href="{{ url_for('reports') }}">
                                <i class="fas fa-chart-bar"></i> التقارير
                            </a>
                        </li>
                        
                        {% if session.is_staff %}
                        <li class="nav-item">
                            <a class="nav-link" href="#">
                                <i class="fas fa-cog"></i> الإعدادات
                            </a>
                        </li>
                        {% endif %}
                    </ul>
                </div>
            </nav>

            <!-- Main content -->
            <main class="col-md-10 ms-sm-auto px-md-4">
                <div class="pt-3 pb-2 mb-3">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    {% block content %}{% endblock %}
                </div>
            </main>
        </div>
    </div>
    {% else %}
        {% block auth_content %}{% endblock %}
    {% endif %}

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
'''

# ==================== ROUTES ====================
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM auth_user WHERE username = ? AND is_active = 1", (username,))
        user = c.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_staff'] = user['is_staff']
            session['is_superuser'] = user['is_superuser']
            
            log_audit('User login')
            conn.close()
            
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('dashboard'))
        
        conn.close()
        flash('خطأ في اسم المستخدم أو كلمة المرور', 'danger')
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block auth_content %}
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h4 class="mb-0">تسجيل الدخول</h4>
                    </div>
                    <div class="card-body">
                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">اسم المستخدم</label>
                                <input type="text" name="username" class="form-control" required autofocus>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">كلمة المرور</label>
                                <input type="password" name="password" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">دخول</button>
                        </form>
                        
                        <hr>
                        <div class="alert alert-info">
                            <strong>بيانات الدخول التجريبية:</strong><br>
                            Admin: admin / admin123<br>
                            Approver: approver / approver123<br>
                            Cashier: cashier / cashier123<br>
                            Auditor: auditor / auditor123
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE)

@app.route('/logout')
def logout():
    log_audit('User logout')
    session.clear()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    c = conn.cursor()
    
    # Get statistics
    stats = {}
    
    # Count cashboxes
    c.execute("SELECT COUNT(*) as count FROM cashbook_cashbox WHERE is_active = 1")
    stats['cashbox_count'] = c.fetchone()['count']
    
    # Today's transactions
    today = date.today()
    c.execute("""SELECT 
                    COUNT(*) as count,
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                 FROM cashbook_cashtransaction 
                 WHERE date = ? AND status = 'approved'""", (today,))
    result = c.fetchone()
    stats['today_count'] = result['count']
    stats['today_income'] = result['income'] or 0
    stats['today_expense'] = result['expense'] or 0
    
    # Pending transactions
    c.execute("SELECT COUNT(*) as count FROM cashbook_cashtransaction WHERE status = 'draft'")
    stats['pending_count'] = c.fetchone()['count']
    
    # Get cashboxes with balances
    c.execute("SELECT * FROM cashbook_cashbox WHERE is_active = 1")
    cashboxes = []
    for box in c.fetchall():
        balance = get_cashbox_balance(box['id'])
        cashboxes.append({
            'id': box['id'],
            'code': box['code'],
            'name': box['name'],
            'currency': box['currency'],
            'balance': float(balance)
        })
    
    # Recent transactions
    c.execute("""SELECT t.*, c.name as cashbox_name, cat.name as category_name, p.name as partner_name
                 FROM cashbook_cashtransaction t
                 LEFT JOIN cashbook_cashbox c ON t.cashbox_id = c.id
                 LEFT JOIN cashbook_category cat ON t.category_id = cat.id
                 LEFT JOIN cashbook_partner p ON t.partner_id = p.id
                 ORDER BY t.created_at DESC
                 LIMIT 10""")
    transactions = c.fetchall()
    
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>لوحة التحكم</h2>
        <div>
            <a href="{{ url_for('transaction_create') }}" class="btn btn-success">
                <i class="fas fa-plus"></i> معاملة جديدة
            </a>
        </div>
    </div>
    
    <!-- Statistics Cards -->
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card stat-card primary">
                <div class="card-body">
                    <h6 class="text-muted">عدد الخزائن</h6>
                    <h3>{{ stats.cashbox_count }}</h3>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card stat-card success">
                <div class="card-body">
                    <h6 class="text-muted">مقبوضات اليوم</h6>
                    <h3>{{ "{:,.2f}".format(stats.today_income) }}</h3>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card stat-card danger">
                <div class="card-body">
                    <h6 class="text-muted">مدفوعات اليوم</h6>
                    <h3>{{ "{:,.2f}".format(stats.today_expense) }}</h3>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card stat-card warning">
                <div class="card-body">
                    <h6 class="text-muted">معاملات معلقة</h6>
                    <h3>{{ stats.pending_count }}</h3>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Cashboxes -->
    <div class="card mb-4">
        <div class="card-header">
            <h5 class="mb-0">أرصدة الخزائن</h5>
        </div>
        <div class="card-body">
            <div class="row">
                {% for box in cashboxes %}
                <div class="col-md-4 mb-3">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">{{ box.name }}</h6>
                            <p class="text-muted mb-1">{{ box.code }}</p>
                            <h4 class="text-primary">{{ "{:,.2f}".format(box.balance) }} {{ box.currency }}</h4>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <!-- Recent Transactions -->
    <div class="card">
        <div class="card-header">
            <h5 class="mb-0">آخر المعاملات</h5>
        </div>
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>رقم السند</th>
                            <th>التاريخ</th>
                            <th>النوع</th>
                            <th>الخزنة</th>
                            <th>المبلغ</th>
                            <th>التصنيف</th>
                            <th>الشريك</th>
                            <th>الحالة</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for txn in transactions %}
                        <tr>
                            <td>{{ txn.voucher_no or '-' }}</td>
                            <td>{{ txn.date }}</td>
                            <td>
                                {% if txn.txn_type == 'receipt' %}
                                    <span class="badge bg-success">قبض</span>
                                {% elif txn.txn_type == 'payment' %}
                                    <span class="badge bg-danger">صرف</span>
                                {% elif txn.txn_type == 'transfer_in' %}
                                    <span class="badge bg-info">تحويل وارد</span>
                                {% else %}
                                    <span class="badge bg-warning">تحويل صادر</span>
                                {% endif %}
                            </td>
                            <td>{{ txn.cashbox_name }}</td>
                            <td>{{ "{:,.2f}".format(txn.amount) }}</td>
                            <td>{{ txn.category_name or '-' }}</td>
                            <td>{{ txn.partner_name or '-' }}</td>
                            <td>
                                {% if txn.status == 'approved' %}
                                    <span class="badge bg-success">معتمد</span>
                                {% elif txn.status == 'draft' %}
                                    <span class="badge bg-warning">مسودة</span>
                                {% else %}
                                    <span class="badge bg-danger">ملغي</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, stats=stats, cashboxes=cashboxes, transactions=transactions)

@app.route('/transactions')
@login_required
def transaction_list():
    conn = get_db()
    c = conn.cursor()
    
    # Build query with filters
    query = """SELECT t.*, c.name as cashbox_name, cat.name as category_name, 
                      p.name as partner_name, u.username as created_by_name
               FROM cashbook_cashtransaction t
               LEFT JOIN cashbook_cashbox c ON t.cashbox_id = c.id
               LEFT JOIN cashbook_category cat ON t.category_id = cat.id
               LEFT JOIN cashbook_partner p ON t.partner_id = p.id
               LEFT JOIN auth_user u ON t.created_by_id = u.id
               WHERE 1=1"""
    
    params = []
    
    # Apply filters
    if request.args.get('search'):
        search = request.args.get('search')
        query += " AND (t.voucher_no LIKE ? OR t.description LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    if request.args.get('status'):
        query += " AND t.status = ?"
        params.append(request.args.get('status'))
    
    if request.args.get('txn_type'):
        query += " AND t.txn_type = ?"
        params.append(request.args.get('txn_type'))
    
    if request.args.get('date_from'):
        query += " AND t.date >= ?"
        params.append(request.args.get('date_from'))
    
    if request.args.get('date_to'):
        query += " AND t.date <= ?"
        params.append(request.args.get('date_to'))
    
    query += " ORDER BY t.created_at DESC LIMIT 200"
    
    c.execute(query, params)
    transactions = c.fetchall()
    
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>المعاملات</h2>
        <div>
            <a href="{{ url_for('transaction_create') }}" class="btn btn-success">
                <i class="fas fa-plus"></i> معاملة جديدة
            </a>
            <a href="{{ url_for('transfer_create') }}" class="btn btn-info">
                <i class="fas fa-exchange-alt"></i> تحويل بين الخزائن
            </a>
        </div>
    </div>
    
    <!-- Filters -->
    <div class="card mb-4">
        <div class="card-body">
            <form method="GET" class="row g-3">
                <div class="col-md-3">
                    <input type="text" name="search" class="form-control" 
                           placeholder="بحث..." value="{{ request.args.get('search', '') }}">
                </div>
                <div class="col-md-2">
                    <select name="txn_type" class="form-select">
                        <option value="">كل الأنواع</option>
                        <option value="receipt" {% if request.args.get('txn_type') == 'receipt' %}selected{% endif %}>قبض</option>
                        <option value="payment" {% if request.args.get('txn_type') == 'payment' %}selected{% endif %}>صرف</option>
                        <option value="transfer_in" {% if request.args.get('txn_type') == 'transfer_in' %}selected{% endif %}>تحويل وارد</option>
                        <option value="transfer_out" {% if request.args.get('txn_type') == 'transfer_out' %}selected{% endif %}>تحويل صادر</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <select name="status" class="form-select">
                        <option value="">كل الحالات</option>
                        <option value="draft" {% if request.args.get('status') == 'draft' %}selected{% endif %}>مسودة</option>
                        <option value="approved" {% if request.args.get('status') == 'approved' %}selected{% endif %}>معتمد</option>
                        <option value="void" {% if request.args.get('status') == 'void' %}selected{% endif %}>ملغي</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <input type="date" name="date_from" class="form-control" 
                           value="{{ request.args.get('date_from', '') }}" placeholder="من تاريخ">
                </div>
                <div class="col-md-2">
                    <input type="date" name="date_to" class="form-control" 
                           value="{{ request.args.get('date_to', '') }}" placeholder="إلى تاريخ">
                </div>
                <div class="col-md-1">
                    <button type="submit" class="btn btn-primary w-100">بحث</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Transactions Table -->
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>رقم السند</th>
                            <th>التاريخ</th>
                            <th>النوع</th>
                            <th>الخزنة</th>
                            <th>المبلغ</th>
                            <th>التصنيف</th>
                            <th>الشريك</th>
                            <th>الوصف</th>
                            <th>الحالة</th>
                            <th>أنشأها</th>
                            <th>إجراءات</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for txn in transactions %}
                        <tr>
                            <td><strong>{{ txn.voucher_no or '-' }}</strong></td>
                            <td>{{ txn.date }}</td>
                            <td>
                                {% if txn.txn_type == 'receipt' %}
                                    <span class="badge bg-success">قبض</span>
                                {% elif txn.txn_type == 'payment' %}
                                    <span class="badge bg-danger">صرف</span>
                                {% elif txn.txn_type == 'transfer_in' %}
                                    <span class="badge bg-info">تحويل وارد</span>
                                {% else %}
                                    <span class="badge bg-warning">تحويل صادر</span>
                                {% endif %}
                            </td>
                            <td>{{ txn.cashbox_name }}</td>
                            <td><strong>{{ "{:,.2f}".format(txn.amount) }}</strong></td>
                            <td>{{ txn.category_name or '-' }}</td>
                            <td>{{ txn.partner_name or '-' }}</td>
                            <td>{{ txn.description[:50] if txn.description else '-' }}</td>
                            <td>
                                {% if txn.status == 'approved' %}
                                    <span class="badge bg-success">معتمد</span>
                                {% elif txn.status == 'draft' %}
                                    <span class="badge bg-warning">مسودة</span>
                                {% else %}
                                    <span class="badge bg-danger">ملغي</span>
                                {% endif %}
                            </td>
                            <td>{{ txn.created_by_name }}</td>
                            <td>
                                <div class="btn-group btn-group-sm">
                                    <a href="{{ url_for('transaction_view', txn_id=txn.id) }}" 
                                       class="btn btn-outline-info" title="عرض">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    {% if txn.status == 'draft' %}
                                        <a href="{{ url_for('transaction_approve', txn_id=txn.id) }}" 
                                           class="btn btn-outline-success" title="اعتماد">
                                            <i class="fas fa-check"></i>
                                        </a>
                                        <a href="{{ url_for('transaction_void', txn_id=txn.id) }}" 
                                           class="btn btn-outline-danger" title="إلغاء">
                                            <i class="fas fa-times"></i>
                                        </a>
                                    {% endif %}
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, transactions=transactions)

@app.route('/transactions/create', methods=['GET', 'POST'])
@login_required
@permission_required('create')
def transaction_create():
    if request.method == 'POST':
        conn = get_db()
        c = conn.cursor()
        
        try:
            # Generate transaction ID and voucher number
            txn_id = str(uuid.uuid4())
            cashbox_id = request.form.get('cashbox_id')
            txn_type = request.form.get('txn_type')
            voucher_no = generate_voucher_no(cashbox_id, txn_type)
            
            # Insert transaction
            c.execute("""INSERT INTO cashbook_cashtransaction 
                        (id, voucher_no, cashbox_id, txn_type, date, category_id, 
                         partner_id, description, amount, created_by_id, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')""",
                      (txn_id, voucher_no, cashbox_id, txn_type,
                       request.form.get('date'), 
                       request.form.get('category_id') or None,
                       request.form.get('partner_id') or None,
                       request.form.get('description'),
                       float(request.form.get('amount')),
                       session['user_id']))
            
            conn.commit()
            log_audit('Create transaction', 'CashTransaction', txn_id)
            
            flash(f'تم إنشاء المعاملة بنجاح - رقم السند: {voucher_no}', 'success')
            return redirect(url_for('transaction_list'))
            
        except Exception as e:
            conn.rollback()
            flash(f'خطأ في إنشاء المعاملة: {str(e)}', 'danger')
        finally:
            conn.close()
    
    # Get form data
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM cashbook_cashbox WHERE is_active = 1")
    cashboxes = c.fetchall()
    
    c.execute("SELECT * FROM cashbook_category WHERE is_active = 1 ORDER BY kind, name")
    categories = c.fetchall()
    
    c.execute("SELECT * FROM cashbook_partner WHERE is_active = 1 ORDER BY name")
    partners = c.fetchall()
    
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="row">
        <div class="col-md-8 mx-auto">
            <div class="card">
                <div class="card-header">
                    <h4 class="mb-0">معاملة جديدة</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">نوع المعاملة *</label>
                                <select name="txn_type" class="form-select" required>
                                    <option value="">اختر...</option>
                                    <option value="receipt">سند قبض</option>
                                    <option value="payment">سند صرف</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">الخزنة *</label>
                                <select name="cashbox_id" class="form-select" required>
                                    <option value="">اختر...</option>
                                    {% for box in cashboxes %}
                                    <option value="{{ box.id }}">{{ box.name }} ({{ box.code }})</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">التاريخ *</label>
                                <input type="date" name="date" class="form-control" 
                                       value="{{ date.today() }}" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">المبلغ *</label>
                                <input type="number" name="amount" class="form-control" 
                                       step="0.01" min="0.01" required>
                            </div>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">التصنيف</label>
                                <select name="category_id" class="form-select">
                                    <option value="">اختر...</option>
                                    {% for cat in categories %}
                                    <option value="{{ cat.id }}">{{ cat.name }} ({{ cat.kind }})</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">الشريك</label>
                                <select name="partner_id" class="form-select">
                                    <option value="">اختر...</option>
                                    {% for partner in partners %}
                                    <option value="{{ partner.id }}">{{ partner.name }} ({{ partner.kind }})</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">الوصف</label>
                            <textarea name="description" class="form-control" rows="3"></textarea>
                        </div>
                        
                        <div class="d-flex justify-content-between">
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-save"></i> حفظ المعاملة
                            </button>
                            <a href="{{ url_for('transaction_list') }}" class="btn btn-secondary">
                                <i class="fas fa-times"></i> إلغاء
                            </a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, cashboxes=cashboxes, categories=categories, 
         partners=partners, date=date)

@app.route('/transactions/<txn_id>')
@login_required
def transaction_view(txn_id):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""SELECT t.*, c.name as cashbox_name, cat.name as category_name, 
                        p.name as partner_name, u1.username as created_by_name,
                        u2.username as approved_by_name
                 FROM cashbook_cashtransaction t
                 LEFT JOIN cashbook_cashbox c ON t.cashbox_id = c.id
                 LEFT JOIN cashbook_category cat ON t.category_id = cat.id
                 LEFT JOIN cashbook_partner p ON t.partner_id = p.id
                 LEFT JOIN auth_user u1 ON t.created_by_id = u1.id
                 LEFT JOIN auth_user u2 ON t.approved_by_id = u2.id
                 WHERE t.id = ?""", (txn_id,))
    
    transaction = c.fetchone()
    conn.close()
    
    if not transaction:
        flash('المعاملة غير موجودة', 'danger')
        return redirect(url_for('transaction_list'))
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="row">
        <div class="col-md-8 mx-auto">
            <div class="card">
                <div class="card-header">
                    <h4 class="mb-0">تفاصيل المعاملة</h4>
                </div>
                <div class="card-body">
                    <dl class="row">
                        <dt class="col-sm-3">رقم السند:</dt>
                        <dd class="col-sm-9"><strong>{{ transaction.voucher_no }}</strong></dd>
                        
                        <dt class="col-sm-3">النوع:</dt>
                        <dd class="col-sm-9">
                            {% if transaction.txn_type == 'receipt' %}
                                <span class="badge bg-success">سند قبض</span>
                            {% elif transaction.txn_type == 'payment' %}
                                <span class="badge bg-danger">سند صرف</span>
                            {% elif transaction.txn_type == 'transfer_in' %}
                                <span class="badge bg-info">تحويل وارد</span>
                            {% else %}
                                <span class="badge bg-warning">تحويل صادر</span>
                            {% endif %}
                        </dd>
                        
                        <dt class="col-sm-3">الحالة:</dt>
                        <dd class="col-sm-9">
                            {% if transaction.status == 'approved' %}
                                <span class="badge bg-success">معتمد</span>
                            {% elif transaction.status == 'draft' %}
                                <span class="badge bg-warning">مسودة</span>
                            {% else %}
                                <span class="badge bg-danger">ملغي</span>
                            {% endif %}
                        </dd>
                        
                        <dt class="col-sm-3">التاريخ:</dt>
                        <dd class="col-sm-9">{{ transaction.date }}</dd>
                        
                        <dt class="col-sm-3">الخزنة:</dt>
                        <dd class="col-sm-9">{{ transaction.cashbox_name }}</dd>
                        
                        <dt class="col-sm-3">المبلغ:</dt>
                        <dd class="col-sm-9"><strong>{{ "{:,.2f}".format(transaction.amount) }} {{ transaction.currency }}</strong></dd>
                        
                        <dt class="col-sm-3">التصنيف:</dt>
                        <dd class="col-sm-9">{{ transaction.category_name or '-' }}</dd>
                        
                        <dt class="col-sm-3">الشريك:</dt>
                        <dd class="col-sm-9">{{ transaction.partner_name or '-' }}</dd>
                        
                        <dt class="col-sm-3">الوصف:</dt>
                        <dd class="col-sm-9">{{ transaction.description or '-' }}</dd>
                        
                        <dt class="col-sm-3">أنشأها:</dt>
                        <dd class="col-sm-9">{{ transaction.created_by_name }}</dd>
                        
                        <dt class="col-sm-3">اعتمدها:</dt>
                        <dd class="col-sm-9">{{ transaction.approved_by_name or '-' }}</dd>
                        
                        <dt class="col-sm-3">تاريخ الإنشاء:</dt>
                        <dd class="col-sm-9">{{ transaction.created_at }}</dd>
                    </dl>
                    
                    <div class="mt-4">
                        {% if transaction.status == 'draft' %}
                            <a href="{{ url_for('transaction_approve', txn_id=transaction.id) }}" 
                               class="btn btn-success">
                                <i class="fas fa-check"></i> اعتماد
                            </a>
                            <a href="{{ url_for('transaction_void', txn_id=transaction.id) }}" 
                               class="btn btn-danger">
                                <i class="fas fa-times"></i> إلغاء
                            </a>
                        {% endif %}
                        <a href="{{ url_for('transaction_list') }}" class="btn btn-secondary">
                            <i class="fas fa-arrow-left"></i> رجوع
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, transaction=transaction)

@app.route('/transactions/<txn_id>/approve')
@login_required
@permission_required('approve')
def transaction_approve(txn_id):
    conn = get_db()
    c = conn.cursor()
    
    try:
        # Check if transaction can be approved
        c.execute("SELECT * FROM cashbook_cashtransaction WHERE id = ? AND status = 'draft'", (txn_id,))
        txn = c.fetchone()
        
        if not txn:
            flash('المعاملة غير موجودة أو تم اعتمادها مسبقاً', 'warning')
        else:
            # Check balance for payment transactions
            if txn['txn_type'] == 'payment':
                balance = get_cashbox_balance(txn['cashbox_id'])
                if balance < Decimal(str(txn['amount'])):
                    flash('الرصيد غير كافي لإتمام عملية الصرف', 'danger')
                    return redirect(url_for('transaction_list'))
            
            # Approve transaction
            c.execute("""UPDATE cashbook_cashtransaction 
                        SET status = 'approved', approved_by_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?""", (session['user_id'], txn_id))
            
            conn.commit()
            log_audit('Approve transaction', 'CashTransaction', txn_id)
            flash('تم اعتماد المعاملة بنجاح', 'success')
            
    except Exception as e:
        conn.rollback()
        flash(f'خطأ في اعتماد المعاملة: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('transaction_list'))

@app.route('/transactions/<txn_id>/void')
@login_required
@permission_required('void')
def transaction_void(txn_id):
    conn = get_db()
    c = conn.cursor()
    
    try:
        c.execute("""UPDATE cashbook_cashtransaction 
                    SET status = 'void', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status != 'void'""", (txn_id,))
        
        if c.rowcount > 0:
            conn.commit()
            log_audit('Void transaction', 'CashTransaction', txn_id)
            flash('تم إلغاء المعاملة', 'warning')
        else:
            flash('المعاملة غير موجودة أو ملغاة مسبقاً', 'warning')
            
    except Exception as e:
        conn.rollback()
        flash(f'خطأ في إلغاء المعاملة: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('transaction_list'))

@app.route('/transfers/create', methods=['GET', 'POST'])
@login_required
@permission_required('create')
def transfer_create():
    if request.method == 'POST':
        from_box_id = request.form.get('from_cashbox_id')
        to_box_id = request.form.get('to_cashbox_id')
        amount = float(request.form.get('amount'))
        description = request.form.get('description')
        
        if from_box_id == to_box_id:
            flash('لا يمكن التحويل من وإلى نفس الخزنة', 'danger')
        else:
            # Check balance
            balance = get_cashbox_balance(from_box_id)
            if balance < Decimal(str(amount)):
                flash('الرصيد غير كافي في الخزنة المحول منها', 'danger')
            else:
                if transfer_between_cashboxes(from_box_id, to_box_id, amount, 
                                             session['user_id'], description):
                    flash('تم التحويل بنجاح', 'success')
                    return redirect(url_for('transaction_list'))
                else:
                    flash('خطأ في عملية التحويل', 'danger')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM cashbook_cashbox WHERE is_active = 1")
    cashboxes = c.fetchall()
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="row">
        <div class="col-md-6 mx-auto">
            <div class="card">
                <div class="card-header">
                    <h4 class="mb-0">تحويل بين الخزائن</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="mb-3">
                            <label class="form-label">من الخزنة *</label>
                            <select name="from_cashbox_id" class="form-select" required>
                                <option value="">اختر...</option>
                                {% for box in cashboxes %}
                                <option value="{{ box.id }}">{{ box.name }} ({{ box.code }})</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">إلى الخزنة *</label>
                            <select name="to_cashbox_id" class="form-select" required>
                                <option value="">اختر...</option>
                                {% for box in cashboxes %}
                                <option value="{{ box.id }}">{{ box.name }} ({{ box.code }})</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">المبلغ *</label>
                            <input type="number" name="amount" class="form-control" 
                                   step="0.01" min="0.01" required>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">الوصف</label>
                            <textarea name="description" class="form-control" rows="3"></textarea>
                        </div>
                        
                        <div class="d-flex justify-content-between">
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-exchange-alt"></i> تنفيذ التحويل
                            </button>
                            <a href="{{ url_for('transaction_list') }}" class="btn btn-secondary">
                                <i class="fas fa-times"></i> إلغاء
                            </a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, cashboxes=cashboxes)

@app.route('/cashboxes')
@login_required
def cashbox_list():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM cashbook_cashbox WHERE is_active = 1")
    cashboxes = []
    
    for box in c.fetchall():
        balance = get_cashbox_balance(box['id'])
        
        # Get today's transactions
        today = date.today()
        c.execute("""SELECT 
                        SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                        SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                     FROM cashbook_cashtransaction 
                     WHERE cashbox_id = ? AND date = ? AND status = 'approved'""", 
                  (box['id'], today))
        result = c.fetchone()
        
        cashboxes.append({
            'id': box['id'],
            'code': box['code'],
            'name': box['name'],
            'currency': box['currency'],
            'opening_balance': box['opening_balance'],
            'balance': float(balance),
            'today_income': result['income'] or 0,
            'today_expense': result['expense'] or 0
        })
    
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>الخزائن</h2>
    </div>
    
    <div class="row">
        {% for box in cashboxes %}
        <div class="col-md-6 mb-4">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">{{ box.name }}</h5>
                </div>
                <div class="card-body">
                    <dl class="row">
                        <dt class="col-sm-5">الكود:</dt>
                        <dd class="col-sm-7">{{ box.code }}</dd>
                        
                        <dt class="col-sm-5">العملة:</dt>
                        <dd class="col-sm-7">{{ box.currency }}</dd>
                        
                        <dt class="col-sm-5">الرصيد الافتتاحي:</dt>
                        <dd class="col-sm-7">{{ "{:,.2f}".format(box.opening_balance) }}</dd>
                        
                        <dt class="col-sm-5">الرصيد الحالي:</dt>
                        <dd class="col-sm-7"><strong class="text-primary">{{ "{:,.2f}".format(box.balance) }}</strong></dd>
                        
                        <dt class="col-sm-5">مقبوضات اليوم:</dt>
                        <dd class="col-sm-7"><span class="text-success">+{{ "{:,.2f}".format(box.today_income) }}</span></dd>
                        
                        <dt class="col-sm-5">مدفوعات اليوم:</dt>
                        <dd class="col-sm-7"><span class="text-danger">-{{ "{:,.2f}".format(box.today_expense) }}</span></dd>
                    </dl>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, cashboxes=cashboxes)

@app.route('/partners')
@login_required
def partner_list():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM cashbook_partner WHERE is_active = 1 ORDER BY name")
    partners = c.fetchall()
    
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>الشركاء</h2>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>الاسم</th>
                            <th>النوع</th>
                            <th>الهاتف</th>
                            <th>البريد الإلكتروني</th>
                            <th>العنوان</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for partner in partners %}
                        <tr>
                            <td>{{ partner.name }}</td>
                            <td>
                                {% if partner.kind == 'customer' %}
                                    <span class="badge bg-success">عميل</span>
                                {% elif partner.kind == 'supplier' %}
                                    <span class="badge bg-warning">مورد</span>
                                {% else %}
                                    <span class="badge bg-info">أخرى</span>
                                {% endif %}
                            </td>
                            <td>{{ partner.phone or '-' }}</td>
                            <td>{{ partner.email or '-' }}</td>
                            <td>{{ partner.address or '-' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, partners=partners)

@app.route('/categories')
@login_required
def category_list():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM cashbook_category WHERE is_active = 1 ORDER BY kind, name")
    categories = c.fetchall()
    
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>التصنيفات</h2>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>الاسم</th>
                            <th>النوع</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for category in categories %}
                        <tr>
                            <td>{{ category.name }}</td>
                            <td>
                                {% if category.kind == 'income' %}
                                    <span class="badge bg-success">إيراد</span>
                                {% elif category.kind == 'expense' %}
                                    <span class="badge bg-danger">مصروف</span>
                                {% else %}
                                    <span class="badge bg-info">تحويل</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, categories=categories)

@app.route('/reports')
@login_required
def reports():
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <h2 class="mb-4">التقارير</h2>
    
    <div class="row">
        <div class="col-md-4 mb-4">
            <div class="card">
                <div class="card-body text-center">
                    <i class="fas fa-calendar-day fa-3x text-primary mb-3"></i>
                    <h5>تقرير الحركة اليومية</h5>
                    <p class="text-muted">عرض جميع المعاملات لليوم</p>
                    <a href="{{ url_for('report_daily') }}" class="btn btn-primary">عرض التقرير</a>
                </div>
            </div>
        </div>
        
        <div class="col-md-4 mb-4">
            <div class="card">
                <div class="card-body text-center">
                    <i class="fas fa-box fa-3x text-success mb-3"></i>
                    <h5>تقرير أرصدة الخزائن</h5>
                    <p class="text-muted">عرض أرصدة جميع الخزائن</p>
                    <a href="{{ url_for('report_cashbox') }}" class="btn btn-success">عرض التقرير</a>
                </div>
            </div>
        </div>
        
        <div class="col-md-4 mb-4">
            <div class="card">
                <div class="card-body text-center">
                    <i class="fas fa-tags fa-3x text-warning mb-3"></i>
                    <h5>تقرير حسب التصنيف</h5>
                    <p class="text-muted">تحليل المعاملات حسب التصنيف</p>
                    <a href="{{ url_for('report_category') }}" class="btn btn-warning">عرض التقرير</a>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE)

@app.route('/reports/daily')
@login_required
def report_daily():
    report_date = request.args.get('date', date.today().isoformat())
    
    conn = get_db()
    c = conn.cursor()
    
    # Get transactions for the day
    c.execute("""SELECT t.*, c.name as cashbox_name, cat.name as category_name, 
                        p.name as partner_name
                 FROM cashbook_cashtransaction t
                 LEFT JOIN cashbook_cashbox c ON t.cashbox_id = c.id
                 LEFT JOIN cashbook_category cat ON t.category_id = cat.id
                 LEFT JOIN cashbook_partner p ON t.partner_id = p.id
                 WHERE t.date = ? AND t.status = 'approved'
                 ORDER BY t.voucher_no""", (report_date,))
    transactions = c.fetchall()
    
    # Calculate totals
    totals = {
        'receipt': 0,
        'payment': 0,
        'transfer_in': 0,
        'transfer_out': 0
    }
    
    for txn in transactions:
        totals[txn['txn_type']] += txn['amount']
    
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>تقرير الحركة اليومية</h2>
        <form method="GET" class="d-flex gap-2">
            <input type="date" name="date" value="{{ report_date }}" class="form-control">
            <button type="submit" class="btn btn-primary">عرض</button>
        </form>
    </div>
    
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card stat-card success">
                <div class="card-body">
                    <h6 class="text-muted">إجمالي المقبوضات</h6>
                    <h4>{{ "{:,.2f}".format(totals.receipt + totals.transfer_in) }}</h4>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card stat-card danger">
                <div class="card-body">
                    <h6 class="text-muted">إجمالي المدفوعات</h6>
                    <h4>{{ "{:,.2f}".format(totals.payment + totals.transfer_out) }}</h4>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card stat-card primary">
                <div class="card-body">
                    <h6 class="text-muted">صافي اليوم</h6>
                    <h4>{{ "{:,.2f}".format((totals.receipt + totals.transfer_in) - (totals.payment + totals.transfer_out)) }}</h4>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card stat-card warning">
                <div class="card-body">
                    <h6 class="text-muted">عدد المعاملات</h6>
                    <h4>{{ transactions|length }}</h4>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h5 class="mb-0">تفاصيل المعاملات - {{ report_date }}</h5>
        </div>
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>رقم السند</th>
                            <th>النوع</th>
                            <th>الخزنة</th>
                            <th>التصنيف</th>
                            <th>الشريك</th>
                            <th>الوصف</th>
                            <th>مدين</th>
                            <th>دائن</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for txn in transactions %}
                        <tr>
                            <td>{{ txn.voucher_no }}</td>
                            <td>
                                {% if txn.txn_type == 'receipt' %}قبض
                                {% elif txn.txn_type == 'payment' %}صرف
                                {% elif txn.txn_type == 'transfer_in' %}تحويل وارد
                                {% else %}تحويل صادر{% endif %}
                            </td>
                            <td>{{ txn.cashbox_name }}</td>
                            <td>{{ txn.category_name or '-' }}</td>
                            <td>{{ txn.partner_name or '-' }}</td>
                            <td>{{ txn.description or '-' }}</td>
                            <td class="text-success">
                                {% if txn.txn_type in ['receipt', 'transfer_in'] %}
                                {{ "{:,.2f}".format(txn.amount) }}
                                {% else %}-{% endif %}
                            </td>
                            <td class="text-danger">
                                {% if txn.txn_type in ['payment', 'transfer_out'] %}
                                {{ "{:,.2f}".format(txn.amount) }}
                                {% else %}-{% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                    <tfoot>
                        <tr class="fw-bold">
                            <td colspan="6">الإجمالي</td>
                            <td class="text-success">{{ "{:,.2f}".format(totals.receipt + totals.transfer_in) }}</td>
                            <td class="text-danger">{{ "{:,.2f}".format(totals.payment + totals.transfer_out) }}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, transactions=transactions, totals=totals, report_date=report_date)

@app.route('/reports/cashbox')
@login_required
def report_cashbox():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM cashbook_cashbox WHERE is_active = 1")
    cashboxes = []
    total_balance = Decimal('0')
    
    for box in c.fetchall():
        balance = get_cashbox_balance(box['id'])
        total_balance += balance
        
        # Get transaction summary
        c.execute("""SELECT 
                        COUNT(*) as count,
                        SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as total_income,
                        SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as total_expense
                     FROM cashbook_cashtransaction 
                     WHERE cashbox_id = ? AND status = 'approved'""", (box['id'],))
        summary = c.fetchone()
        
        cashboxes.append({
            'code': box['code'],
            'name': box['name'],
            'currency': box['currency'],
            'opening_balance': box['opening_balance'],
            'total_income': summary['total_income'] or 0,
            'total_expense': summary['total_expense'] or 0,
            'balance': float(balance),
            'txn_count': summary['count']
        })
    
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>تقرير أرصدة الخزائن</h2>
        <button onclick="window.print()" class="btn btn-secondary">
            <i class="fas fa-print"></i> طباعة
        </button>
    </div>
    
    <div class="card mb-4">
        <div class="card-body">
            <h4 class="text-center">إجمالي الأرصدة: <span class="text-primary">{{ "{:,.2f}".format(total_balance) }} EGP</span></h4>
        </div>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>الكود</th>
                            <th>اسم الخزنة</th>
                            <th>العملة</th>
                            <th>الرصيد الافتتاحي</th>
                            <th>إجمالي المقبوضات</th>
                            <th>إجمالي المدفوعات</th>
                            <th>الرصيد الحالي</th>
                            <th>عدد المعاملات</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for box in cashboxes %}
                        <tr>
                            <td><strong>{{ box.code }}</strong></td>
                            <td>{{ box.name }}</td>
                            <td>{{ box.currency }}</td>
                            <td>{{ "{:,.2f}".format(box.opening_balance) }}</td>
                            <td class="text-success">{{ "{:,.2f}".format(box.total_income) }}</td>
                            <td class="text-danger">{{ "{:,.2f}".format(box.total_expense) }}</td>
                            <td><strong class="text-primary">{{ "{:,.2f}".format(box.balance) }}</strong></td>
                            <td>{{ box.txn_count }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, cashboxes=cashboxes, total_balance=float(total_balance))

@app.route('/reports/category')
@login_required
def report_category():
    conn = get_db()
    c = conn.cursor()
    
    # Get category summary
    c.execute("""SELECT c.id, c.name, c.kind,
                        COUNT(t.id) as txn_count,
                        SUM(t.amount) as total_amount
                 FROM cashbook_category c
                 LEFT JOIN cashbook_cashtransaction t ON c.id = t.category_id AND t.status = 'approved'
                 WHERE c.is_active = 1
                 GROUP BY c.id, c.name, c.kind
                 ORDER BY c.kind, total_amount DESC""")
    
    categories = c.fetchall()
    conn.close()
    
    return render_template_string('''
    {% extends "base.html" %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>تقرير حسب التصنيف</h2>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>التصنيف</th>
                            <th>النوع</th>
                            <th>عدد المعاملات</th>
                            <th>إجمالي المبلغ</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for cat in categories %}
                        <tr>
                            <td>{{ cat.name }}</td>
                            <td>
                                {% if cat.kind == 'income' %}
                                    <span class="badge bg-success">إيراد</span>
                                {% elif cat.kind == 'expense' %}
                                    <span class="badge bg-danger">مصروف</span>
                                {% else %}
                                    <span class="badge bg-info">تحويل</span>
                                {% endif %}
                            </td>
                            <td>{{ cat.txn_count }}</td>
                            <td><strong>{{ "{:,.2f}".format(cat.total_amount or 0) }}</strong></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endblock %}
    ''', base=BASE_TEMPLATE, categories=categories)

# Run the application
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
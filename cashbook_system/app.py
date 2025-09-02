#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
import uuid
from datetime import datetime, date
from flask import Flask, render_template_string, request, redirect, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'cashbook-professional-2024'

# Create directories
os.makedirs('instance', exist_ok=True)
os.makedirs('uploads', exist_ok=True)

# Database initialization
def init_database():
    """Initialize database with all tables"""
    conn = sqlite3.connect('instance/cashbook.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS auth_user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        first_name TEXT,
        last_name TEXT,
        is_active INTEGER DEFAULT 1,
        is_staff INTEGER DEFAULT 0,
        is_superuser INTEGER DEFAULT 0,
        date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Groups table
    c.execute('''CREATE TABLE IF NOT EXISTS auth_group (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )''')
    
    # User groups
    c.execute('''CREATE TABLE IF NOT EXISTS auth_user_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES auth_user(id),
        FOREIGN KEY (group_id) REFERENCES auth_group(id),
        UNIQUE(user_id, group_id)
    )''')
    
    # CashBox table
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_cashbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        currency TEXT DEFAULT 'EGP',
        opening_balance REAL DEFAULT 0.00,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Partner table
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_partner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT DEFAULT 'other',
        phone TEXT,
        email TEXT,
        address TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Category table
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_category (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        parent_id INTEGER,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES cashbook_category(id)
    )''')
    
    # CashTransaction table
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_cashtransaction (
        id TEXT PRIMARY KEY,
        cashbox_id INTEGER NOT NULL,
        txn_type TEXT NOT NULL,
        status TEXT DEFAULT 'draft',
        date DATE NOT NULL,
        category_id INTEGER,
        partner_id INTEGER,
        description TEXT,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'EGP',
        rate_to_base REAL DEFAULT 1.000000,
        voucher_no TEXT UNIQUE,
        created_by_id INTEGER NOT NULL,
        approved_by_id INTEGER,
        linked_txn_id TEXT,
        attachment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashbook_cashbox(id),
        FOREIGN KEY (category_id) REFERENCES cashbook_category(id),
        FOREIGN KEY (partner_id) REFERENCES cashbook_partner(id),
        FOREIGN KEY (created_by_id) REFERENCES auth_user(id),
        FOREIGN KEY (approved_by_id) REFERENCES auth_user(id),
        FOREIGN KEY (linked_txn_id) REFERENCES cashbook_cashtransaction(id)
    )''')
    
    # PeriodClose table
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_periodclose (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cashbox_id INTEGER NOT NULL,
        month INTEGER NOT NULL,
        year INTEGER NOT NULL,
        closed_by_id INTEGER NOT NULL,
        closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashbook_cashbox(id),
        FOREIGN KEY (closed_by_id) REFERENCES auth_user(id),
        UNIQUE(cashbox_id, month, year)
    )''')
    
    # Audit log table
    c.execute('''CREATE TABLE IF NOT EXISTS cashbook_auditlog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        model_name TEXT,
        object_id TEXT,
        changes TEXT,
        ip_address TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES auth_user(id)
    )''')
    
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
        
        # Create users
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
            (1, 1),  # admin -> Admin
            (2, 2),  # approver -> Approver
            (3, 3),  # cashier -> Cashier
            (4, 4),  # auditor -> Auditor
        ]
        c.executemany("INSERT INTO auth_user_groups (user_id, group_id) VALUES (?, ?)", user_groups)
        
        # Create CashBoxes
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
        
        # Create Categories
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
        
        # Create Partners
        partners = [
            ('عميل نقدي', 'customer', '01000000000', 'cash@customer.com', 'نقدي'),
            ('شركة الأمل للتجارة', 'customer', '01234567890', 'amal@company.com', 'القاهرة'),
            ('مؤسسة النور', 'customer', '01098765432', 'nour@foundation.org', 'الإسكندرية'),
            ('شركة التوريدات المتحدة', 'supplier', '01111111111', 'united@supplies.com', 'القاهرة'),
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

# Helper functions
def get_db():
    conn = sqlite3.connect('instance/cashbook.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def generate_voucher_no(cashbox_id, txn_type):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT code FROM cashbook_cashbox WHERE id = ?", (cashbox_id,))
    cashbox = c.fetchone()
    if not cashbox:
        conn.close()
        return None
    
    year = datetime.now().year
    prefix = f"{cashbox['code']}-{year}"
    
    c.execute("""SELECT voucher_no FROM cashbook_cashtransaction 
                WHERE voucher_no LIKE ? 
                ORDER BY voucher_no DESC LIMIT 1""", (f"{prefix}-%",))
    last = c.fetchone()
    
    if last:
        seq = int(last['voucher_no'].split('-')[-1]) + 1
    else:
        seq = 1
    
    conn.close()
    return f"{prefix}-{seq:06d}"

def get_cashbox_balance(cashbox_id):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT opening_balance FROM cashbook_cashbox WHERE id = ?", (cashbox_id,))
    result = c.fetchone()
    if not result:
        conn.close()
        return 0.0
    
    opening_balance = float(result['opening_balance'])
    
    c.execute("""SELECT 
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as in_sum,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as out_sum
                 FROM cashbook_cashtransaction 
                 WHERE cashbox_id = ? AND status = 'approved'""", (cashbox_id,))
    result = c.fetchone()
    
    in_sum = float(result['in_sum'] or 0)
    out_sum = float(result['out_sum'] or 0)
    
    conn.close()
    return opening_balance + in_sum - out_sum

# Base HTML template
BASE_HTML = '''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نظام إدارة الخزينة</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; }
        .navbar-brand { font-weight: bold; font-size: 1.5rem; }
        .sidebar { min-height: calc(100vh - 56px); background: linear-gradient(180deg, #343a40 0%, #495057 100%); }
        .sidebar .nav-link { color: rgba(255,255,255,0.8); padding: 1rem; transition: all 0.3s; }
        .sidebar .nav-link:hover { color: white; background-color: rgba(255,255,255,0.1); }
        .sidebar .nav-link.active { color: white; background-color: #007bff; }
        .card { border: none; box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075); margin-bottom: 1.5rem; }
        .stat-card { border-left: 4px solid; transition: transform 0.3s; }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-card.primary { border-left-color: #007bff; }
        .stat-card.success { border-left-color: #28a745; }
        .stat-card.warning { border-left-color: #ffc107; }
        .stat-card.danger { border-left-color: #dc3545; }
    </style>
</head>
<body>
    {{ content | safe }}
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    return redirect('/dashboard')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM auth_user WHERE username = ? AND is_active = 1", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_staff'] = user['is_staff']
            session['is_superuser'] = user['is_superuser']
            return redirect('/dashboard')
        
        error = 'خطأ في اسم المستخدم أو كلمة المرور'
    
    content = f'''
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h4 class="mb-0">تسجيل الدخول - نظام إدارة الخزينة</h4>
                    </div>
                    <div class="card-body">
                        {'<div class="alert alert-danger">' + error + '</div>' if error else ''}
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
    '''
    
    return render_template_string(BASE_HTML, content=content)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    c = conn.cursor()
    
    # Get statistics
    c.execute("SELECT COUNT(*) as count FROM cashbook_cashbox WHERE is_active = 1")
    cashbox_count = c.fetchone()['count']
    
    today = date.today()
    c.execute("""SELECT 
                    COUNT(*) as count,
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                 FROM cashbook_cashtransaction 
                 WHERE date = ? AND status = 'approved'""", (today,))
    result = c.fetchone()
    today_income = result['income'] or 0
    today_expense = result['expense'] or 0
    
    c.execute("SELECT COUNT(*) as count FROM cashbook_cashtransaction WHERE status = 'draft'")
    pending_count = c.fetchone()['count']
    
    # Get cashboxes
    c.execute("SELECT * FROM cashbook_cashbox WHERE is_active = 1")
    cashboxes = []
    for box in c.fetchall():
        balance = get_cashbox_balance(box['id'])
        cashboxes.append({
            'code': box['code'],
            'name': box['name'],
            'currency': box['currency'],
            'balance': balance
        })
    
    # Get recent transactions
    c.execute("""SELECT t.*, c.name as cashbox_name
                 FROM cashbook_cashtransaction t
                 LEFT JOIN cashbook_cashbox c ON t.cashbox_id = c.id
                 ORDER BY t.created_at DESC
                 LIMIT 10""")
    transactions = c.fetchall()
    
    conn.close()
    
    # Build navbar
    navbar = f'''
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-cash-register"></i> نظام إدارة الخزينة
            </a>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text text-white me-3">
                    <i class="fas fa-user"></i> {session['username']}
                </span>
                <a class="btn btn-outline-light btn-sm" href="/logout">خروج</a>
            </div>
        </div>
    </nav>
    '''
    
    # Build sidebar
    sidebar = '''
    <nav class="col-md-2 d-md-block sidebar">
        <div class="position-sticky pt-3">
            <ul class="nav flex-column">
                <li class="nav-item">
                    <a class="nav-link active" href="/dashboard">
                        <i class="fas fa-tachometer-alt"></i> لوحة التحكم
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/transactions">
                        <i class="fas fa-exchange-alt"></i> المعاملات
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/cashboxes">
                        <i class="fas fa-box"></i> الخزائن
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/partners">
                        <i class="fas fa-users"></i> الشركاء
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/categories">
                        <i class="fas fa-tags"></i> التصنيفات
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/reports">
                        <i class="fas fa-chart-bar"></i> التقارير
                    </a>
                </li>
            </ul>
        </div>
    </nav>
    '''
    
    # Build main content
    main_content = f'''
    <main class="col-md-10 ms-sm-auto px-md-4">
        <div class="pt-3 pb-2 mb-3">
            <h2>لوحة التحكم</h2>
            
            <div class="row mb-4 mt-4">
                <div class="col-md-3">
                    <div class="card stat-card primary">
                        <div class="card-body">
                            <h6 class="text-muted">عدد الخزائن</h6>
                            <h3>{cashbox_count}</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card stat-card success">
                        <div class="card-body">
                            <h6 class="text-muted">مقبوضات اليوم</h6>
                            <h3>{today_income:,.2f}</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card stat-card danger">
                        <div class="card-body">
                            <h6 class="text-muted">مدفوعات اليوم</h6>
                            <h3>{today_expense:,.2f}</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card stat-card warning">
                        <div class="card-body">
                            <h6 class="text-muted">معاملات معلقة</h6>
                            <h3>{pending_count}</h3>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">أرصدة الخزائن</h5>
                </div>
                <div class="card-body">
                    <div class="row">
    '''
    
    for box in cashboxes:
        main_content += f'''
                        <div class="col-md-4 mb-3">
                            <div class="card">
                                <div class="card-body">
                                    <h6 class="card-title">{box['name']}</h6>
                                    <p class="text-muted mb-1">{box['code']}</p>
                                    <h4 class="text-primary">{box['balance']:,.2f} {box['currency']}</h4>
                                </div>
                            </div>
                        </div>
        '''
    
    main_content += '''
                    </div>
                </div>
            </div>
            
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
                                    <th>الحالة</th>
                                </tr>
                            </thead>
                            <tbody>
    '''
    
    for txn in transactions:
        type_badge = {
            'receipt': '<span class="badge bg-success">قبض</span>',
            'payment': '<span class="badge bg-danger">صرف</span>',
            'transfer_in': '<span class="badge bg-info">تحويل وارد</span>',
            'transfer_out': '<span class="badge bg-warning">تحويل صادر</span>'
        }.get(txn['txn_type'], txn['txn_type'])
        
        status_badge = {
            'approved': '<span class="badge bg-success">معتمد</span>',
            'draft': '<span class="badge bg-warning">مسودة</span>',
            'void': '<span class="badge bg-danger">ملغي</span>'
        }.get(txn['status'], txn['status'])
        
        main_content += f'''
                                <tr>
                                    <td>{txn['voucher_no'] or '-'}</td>
                                    <td>{txn['date']}</td>
                                    <td>{type_badge}</td>
                                    <td>{txn['cashbox_name']}</td>
                                    <td>{txn['amount']:,.2f}</td>
                                    <td>{status_badge}</td>
                                </tr>
        '''
    
    main_content += '''
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </main>
    '''
    
    content = navbar + '<div class="container-fluid"><div class="row">' + sidebar + main_content + '</div></div>'
    
    return render_template_string(BASE_HTML, content=content)

@app.route('/transactions')
@login_required
def transactions():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""SELECT t.*, c.name as cashbox_name
                 FROM cashbook_cashtransaction t
                 LEFT JOIN cashbook_cashbox c ON t.cashbox_id = c.id
                 ORDER BY t.created_at DESC
                 LIMIT 100""")
    transactions = c.fetchall()
    conn.close()
    
    navbar = f'''
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-cash-register"></i> نظام إدارة الخزينة
            </a>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text text-white me-3">
                    <i class="fas fa-user"></i> {session['username']}
                </span>
                <a class="btn btn-outline-light btn-sm" href="/logout">خروج</a>
            </div>
        </div>
    </nav>
    '''
    
    sidebar = '''
    <nav class="col-md-2 d-md-block sidebar">
        <div class="position-sticky pt-3">
            <ul class="nav flex-column">
                <li class="nav-item">
                    <a class="nav-link" href="/dashboard">
                        <i class="fas fa-tachometer-alt"></i> لوحة التحكم
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link active" href="/transactions">
                        <i class="fas fa-exchange-alt"></i> المعاملات
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/cashboxes">
                        <i class="fas fa-box"></i> الخزائن
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/partners">
                        <i class="fas fa-users"></i> الشركاء
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/categories">
                        <i class="fas fa-tags"></i> التصنيفات
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/reports">
                        <i class="fas fa-chart-bar"></i> التقارير
                    </a>
                </li>
            </ul>
        </div>
    </nav>
    '''
    
    main_content = '''
    <main class="col-md-10 ms-sm-auto px-md-4">
        <div class="pt-3 pb-2 mb-3">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h2>المعاملات</h2>
                <div>
                    <a href="/transaction/create" class="btn btn-success">
                        <i class="fas fa-plus"></i> معاملة جديدة
                    </a>
                </div>
            </div>
            
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
                                    <th>الوصف</th>
                                    <th>الحالة</th>
                                    <th>إجراءات</th>
                                </tr>
                            </thead>
                            <tbody>
    '''
    
    for txn in transactions:
        type_badge = {
            'receipt': '<span class="badge bg-success">قبض</span>',
            'payment': '<span class="badge bg-danger">صرف</span>',
            'transfer_in': '<span class="badge bg-info">تحويل وارد</span>',
            'transfer_out': '<span class="badge bg-warning">تحويل صادر</span>'
        }.get(txn['txn_type'], txn['txn_type'])
        
        status_badge = {
            'approved': '<span class="badge bg-success">معتمد</span>',
            'draft': '<span class="badge bg-warning">مسودة</span>',
            'void': '<span class="badge bg-danger">ملغي</span>'
        }.get(txn['status'], txn['status'])
        
        main_content += f'''
                                <tr>
                                    <td>{txn['voucher_no'] or '-'}</td>
                                    <td>{txn['date']}</td>
                                    <td>{type_badge}</td>
                                    <td>{txn['cashbox_name']}</td>
                                    <td>{txn['amount']:,.2f}</td>
                                    <td>{txn['description'][:50] if txn['description'] else '-'}</td>
                                    <td>{status_badge}</td>
                                    <td>
                                        <div class="btn-group btn-group-sm">
                                            <a href="#" class="btn btn-outline-info">عرض</a>
        '''
        
        if txn['status'] == 'draft':
            main_content += '''
                                            <a href="#" class="btn btn-outline-success">اعتماد</a>
            '''
        
        main_content += '''
                                        </div>
                                    </td>
                                </tr>
        '''
    
    main_content += '''
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </main>
    '''
    
    content = navbar + '<div class="container-fluid"><div class="row">' + sidebar + main_content + '</div></div>'
    
    return render_template_string(BASE_HTML, content=content)

@app.route('/cashboxes')
@login_required
def cashboxes():
    return redirect('/dashboard')

@app.route('/partners')
@login_required
def partners():
    return redirect('/dashboard')

@app.route('/categories')
@login_required
def categories():
    return redirect('/dashboard')

@app.route('/reports')
@login_required
def reports():
    return redirect('/dashboard')

@app.route('/transaction/create')
@login_required
def transaction_create():
    return redirect('/transactions')

# Health check
@app.route('/health')
def health():
    return 'OK'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
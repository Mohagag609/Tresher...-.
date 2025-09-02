#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
import uuid
from flask import Flask, render_template_string, request, redirect, session, jsonify, send_file, flash
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import io
import csv

app = Flask(__name__)
app.secret_key = 'cashbook-professional-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('instance', exist_ok=True)

# Database initialization
def init_db():
    """Initialize database with all tables"""
    conn = sqlite3.connect('instance/cashbook.db')
    c = conn.cursor()
    
    # Users table with roles
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        fullname TEXT,
        role TEXT DEFAULT 'cashier',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Cash boxes table
    c.execute('''CREATE TABLE IF NOT EXISTS cashboxes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        currency TEXT DEFAULT 'EGP',
        opening_balance REAL DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Partners table
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT DEFAULT 'other',
        phone TEXT,
        email TEXT,
        address TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Categories table
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        parent_id INTEGER,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES categories(id)
    )''')
    
    # Transactions table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        voucher_no TEXT UNIQUE,
        cashbox_id INTEGER NOT NULL,
        txn_type TEXT NOT NULL,
        status TEXT DEFAULT 'draft',
        txn_date DATE NOT NULL,
        category_id INTEGER,
        partner_id INTEGER,
        description TEXT,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'EGP',
        exchange_rate REAL DEFAULT 1,
        created_by INTEGER NOT NULL,
        approved_by INTEGER,
        linked_txn_id TEXT,
        attachment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashboxes(id),
        FOREIGN KEY (category_id) REFERENCES categories(id),
        FOREIGN KEY (partner_id) REFERENCES partners(id),
        FOREIGN KEY (created_by) REFERENCES users(id),
        FOREIGN KEY (approved_by) REFERENCES users(id)
    )''')
    
    # Audit log table
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        table_name TEXT,
        record_id TEXT,
        old_values TEXT,
        new_values TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Period close table
    c.execute('''CREATE TABLE IF NOT EXISTS period_closes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cashbox_id INTEGER NOT NULL,
        month INTEGER NOT NULL,
        year INTEGER NOT NULL,
        closed_by INTEGER NOT NULL,
        closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashboxes(id),
        FOREIGN KEY (closed_by) REFERENCES users(id),
        UNIQUE(cashbox_id, month, year)
    )''')
    
    # Check if we need to add default data
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        # Add default users
        users = [
            ('admin', generate_password_hash('admin123'), 'مدير النظام', 'admin'),
            ('approver', generate_password_hash('approver123'), 'المعتمد', 'approver'),
            ('cashier', generate_password_hash('cashier123'), 'أمين الصندوق', 'cashier'),
            ('auditor', generate_password_hash('auditor123'), 'المراجع', 'auditor')
        ]
        c.executemany("INSERT INTO users (username, password, fullname, role) VALUES (?, ?, ?, ?)", users)
        
        # Add default cashboxes
        cashboxes = [
            ('MAIN', 'الخزنة الرئيسية', 'EGP', 50000),
            ('PETTY', 'العهدة النثرية', 'EGP', 5000),
            ('BANK', 'الحساب البنكي', 'EGP', 100000),
            ('BRANCH1', 'خزنة الفرع الأول', 'EGP', 20000)
        ]
        c.executemany("INSERT INTO cashboxes (code, name, currency, opening_balance) VALUES (?, ?, ?, ?)", cashboxes)
        
        # Add default categories
        categories = [
            ('مبيعات', 'income'),
            ('خدمات', 'income'),
            ('إيرادات أخرى', 'income'),
            ('رواتب', 'expense'),
            ('إيجار', 'expense'),
            ('مصروفات إدارية', 'expense'),
            ('مشتريات', 'expense'),
            ('تحويلات', 'transfer')
        ]
        c.executemany("INSERT INTO categories (name, kind) VALUES (?, ?)", categories)
        
        # Add default partners
        partners = [
            ('عميل نقدي', 'customer', '', ''),
            ('شركة ABC', 'customer', '01234567890', 'abc@example.com'),
            ('مورد XYZ', 'supplier', '01098765432', 'xyz@example.com'),
            ('شركة الكهرباء', 'supplier', '19999', ''),
            ('موظف أحمد محمد', 'other', '01111111111', '')
        ]
        c.executemany("INSERT INTO partners (name, kind, phone, email) VALUES (?, ?, ?, ?)", partners)
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Helper functions
def get_db():
    conn = sqlite3.connect('instance/cashbook.db')
    conn.row_factory = sqlite3.Row
    return conn

def log_audit(user_id, action, table_name=None, record_id=None, old_values=None, new_values=None):
    """Log audit trail"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values, ip_address)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (user_id, action, table_name, record_id, 
               json.dumps(old_values) if old_values else None,
               json.dumps(new_values) if new_values else None,
               request.remote_addr))
    conn.commit()
    conn.close()

def generate_voucher_no(cashbox_id, txn_type):
    """Generate automatic voucher number"""
    conn = get_db()
    c = conn.cursor()
    
    # Get cashbox code
    c.execute("SELECT code FROM cashboxes WHERE id = ?", (cashbox_id,))
    cashbox = c.fetchone()
    if not cashbox:
        return None
    
    # Generate prefix based on type and year
    year = datetime.now().year
    type_prefix = {'receipt': 'REC', 'payment': 'PAY', 'transfer_out': 'TRO', 'transfer_in': 'TRI'}
    prefix = f"{cashbox['code']}-{type_prefix.get(txn_type, 'TXN')}-{year}"
    
    # Get next sequence
    c.execute("SELECT voucher_no FROM transactions WHERE voucher_no LIKE ? ORDER BY voucher_no DESC LIMIT 1", 
              (f"{prefix}-%",))
    last = c.fetchone()
    
    if last:
        seq = int(last['voucher_no'].split('-')[-1]) + 1
    else:
        seq = 1
    
    conn.close()
    return f"{prefix}-{seq:06d}"

def get_cashbox_balance(cashbox_id):
    """Calculate current balance for a cashbox"""
    conn = get_db()
    c = conn.cursor()
    
    # Get opening balance
    c.execute("SELECT opening_balance FROM cashboxes WHERE id = ?", (cashbox_id,))
    result = c.fetchone()
    if not result:
        return 0
    
    opening = result['opening_balance']
    
    # Calculate transactions
    c.execute("""SELECT 
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                 FROM transactions 
                 WHERE cashbox_id = ? AND status = 'approved'""", (cashbox_id,))
    result = c.fetchone()
    
    income = result['income'] or 0
    expense = result['expense'] or 0
    
    conn.close()
    return opening + income - expense

def check_permission(role, action):
    """Check user permissions based on role"""
    permissions = {
        'admin': ['all'],
        'approver': ['view', 'create', 'approve', 'void'],
        'cashier': ['view', 'create', 'edit_draft'],
        'auditor': ['view', 'reports']
    }
    
    if role == 'admin':
        return True
    
    return action in permissions.get(role, [])

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - نظام إدارة الخزينة</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, 'Segoe UI', 'Arial', sans-serif;
            background: #f5f6fa;
            min-height: 100vh;
        }
        
        /* Header */
        .header {
            background: white;
            padding: 15px 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            color: #333;
            font-size: 24px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .user-menu {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .user-info {
            display: flex;
            flex-direction: column;
            align-items: end;
        }
        
        .user-name {
            font-weight: bold;
            color: #333;
        }
        
        .user-role {
            font-size: 12px;
            color: #666;
            background: #f0f0f0;
            padding: 2px 8px;
            border-radius: 10px;
            margin-top: 2px;
        }
        
        /* Navigation */
        .nav {
            background: #2c3e50;
            padding: 0;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .nav ul {
            list-style: none;
            display: flex;
            padding: 0 20px;
        }
        
        .nav li {
            position: relative;
        }
        
        .nav a {
            display: block;
            padding: 15px 20px;
            color: white;
            text-decoration: none;
            transition: background 0.3s;
        }
        
        .nav a:hover {
            background: #34495e;
        }
        
        .nav .active {
            background: #3498db;
        }
        
        /* Dropdown */
        .dropdown {
            position: relative;
        }
        
        .dropdown-content {
            display: none;
            position: absolute;
            background: white;
            min-width: 200px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            z-index: 1000;
            right: 0;
            border-radius: 5px;
            overflow: hidden;
        }
        
        .dropdown:hover .dropdown-content {
            display: block;
        }
        
        .dropdown-content a {
            color: #333;
            padding: 12px 16px;
            display: block;
        }
        
        .dropdown-content a:hover {
            background: #f1f1f1;
        }
        
        /* Container */
        .container {
            padding: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        /* Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-card.primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .stat-card.success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }
        
        .stat-card.warning {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        
        .stat-card h3 {
            font-size: 14px;
            margin-bottom: 10px;
            opacity: 0.9;
        }
        
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
        }
        
        .stat-card .unit {
            font-size: 14px;
            opacity: 0.7;
        }
        
        /* Tables */
        .table-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            overflow: hidden;
            margin-bottom: 30px;
        }
        
        .table-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            font-size: 18px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            background: #f8f9fa;
            padding: 15px;
            text-align: right;
            font-weight: 600;
            color: #666;
            border-bottom: 2px solid #e0e0e0;
        }
        
        td {
            padding: 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        
        tr:hover {
            background: #fafbfc;
        }
        
        /* Badges */
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge.success {
            background: #d4edda;
            color: #155724;
        }
        
        .badge.warning {
            background: #fff3cd;
            color: #856404;
        }
        
        .badge.danger {
            background: #f8d7da;
            color: #721c24;
        }
        
        .badge.info {
            background: #d1ecf1;
            color: #0c5460;
        }
        
        /* Forms */
        .form-container {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            max-width: 800px;
            margin: 0 auto;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: #666;
            font-weight: 500;
        }
        
        .form-control {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .form-control:focus {
            outline: none;
            border-color: #667eea;
        }
        
        select.form-control {
            cursor: pointer;
        }
        
        textarea.form-control {
            resize: vertical;
            min-height: 100px;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        /* Buttons */
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-success {
            background: #28a745;
            color: white;
        }
        
        .btn-danger {
            background: #dc3545;
            color: white;
        }
        
        .btn-warning {
            background: #ffc107;
            color: #333;
        }
        
        .btn-info {
            background: #17a2b8;
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .btn-group {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        /* Login */
        .login-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .login-box {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 400px;
        }
        
        .login-box h2 {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }
        
        /* Alerts */
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .alert-danger {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .alert-warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeeba;
        }
        
        /* Actions */
        .actions {
            display: flex;
            gap: 5px;
        }
        
        .btn-sm {
            padding: 5px 10px;
            font-size: 12px;
        }
        
        /* Search bar */
        .search-bar {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .search-bar input {
            flex: 1;
        }
        
        /* Quick actions */
        .quick-actions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .quick-action {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            text-decoration: none;
            color: #333;
            transition: all 0.3s;
            border: 2px solid transparent;
        }
        
        .quick-action:hover {
            border-color: #667eea;
            transform: translateY(-3px);
        }
        
        .quick-action i {
            font-size: 36px;
            margin-bottom: 10px;
            color: #667eea;
        }
    </style>
</head>
<body>
    {% if not hide_header %}
    <div class="header">
        <h1>💰 نظام إدارة الخزينة المتقدم</h1>
        <div class="user-menu">
            <div class="user-info">
                <span class="user-name">{{ session.fullname }}</span>
                <span class="user-role">{{ session.role }}</span>
            </div>
            <a href="/logout" class="btn btn-danger btn-sm">خروج</a>
        </div>
    </div>
    
    <nav class="nav">
        <ul>
            <li><a href="/dashboard" class="{{ 'active' if page == 'dashboard' }}">🏠 الرئيسية</a></li>
            
            <li class="dropdown">
                <a href="#">💵 المعاملات</a>
                <div class="dropdown-content">
                    <a href="/transactions">📋 عرض المعاملات</a>
                    <a href="/transactions/new">➕ معاملة جديدة</a>
                    <a href="/transfers">🔄 التحويلات</a>
                </div>
            </li>
            
            <li class="dropdown">
                <a href="#">📦 الخزائن</a>
                <div class="dropdown-content">
                    <a href="/cashboxes">📊 عرض الخزائن</a>
                    {% if session.role == 'admin' %}
                    <a href="/cashboxes/new">➕ خزنة جديدة</a>
                    {% endif %}
                </div>
            </li>
            
            <li class="dropdown">
                <a href="#">👥 الشركاء</a>
                <div class="dropdown-content">
                    <a href="/partners">📋 عرض الشركاء</a>
                    <a href="/partners/new">➕ شريك جديد</a>
                </div>
            </li>
            
            <li class="dropdown">
                <a href="#">🏷️ التصنيفات</a>
                <div class="dropdown-content">
                    <a href="/categories">📋 عرض التصنيفات</a>
                    {% if session.role == 'admin' %}
                    <a href="/categories/new">➕ تصنيف جديد</a>
                    {% endif %}
                </div>
            </li>
            
            <li class="dropdown">
                <a href="#">📊 التقارير</a>
                <div class="dropdown-content">
                    <a href="/reports/daily">📅 الحركة اليومية</a>
                    <a href="/reports/cashbox">💰 أرصدة الخزائن</a>
                    <a href="/reports/category">🏷️ حسب التصنيف</a>
                    <a href="/reports/partner">👥 حسب الشريك</a>
                    <a href="/reports/audit">🔍 سجل المراجعة</a>
                </div>
            </li>
            
            {% if session.role == 'admin' %}
            <li class="dropdown">
                <a href="#">⚙️ الإعدادات</a>
                <div class="dropdown-content">
                    <a href="/users">👤 المستخدمين</a>
                    <a href="/period-close">🔒 إغلاق الفترة</a>
                    <a href="/backup">💾 النسخ الاحتياطي</a>
                </div>
            </li>
            {% endif %}
        </ul>
    </nav>
    {% endif %}
    
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>
</body>
</html>
'''

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    return redirect('/dashboard')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
        user = c.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['fullname'] = user['fullname']
            session['role'] = user['role']
            
            log_audit(user['id'], 'تسجيل دخول')
            conn.close()
            return redirect('/dashboard')
        
        conn.close()
        error = 'خطأ في اسم المستخدم أو كلمة المرور'
    else:
        error = None
    
    login_html = '''
    {% extends HTML_TEMPLATE %}
    {% block content %}
    <div class="login-container">
        <div class="login-box">
            <h2>🏦 نظام إدارة الخزينة</h2>
            {% if error %}
            <div class="alert alert-danger">{{ error }}</div>
            {% endif %}
            <form method="POST">
                <div class="form-group">
                    <label>اسم المستخدم</label>
                    <input type="text" name="username" class="form-control" required autofocus>
                </div>
                <div class="form-group">
                    <label>كلمة المرور</label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%">دخول</button>
            </form>
            <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <strong>بيانات الدخول التجريبية:</strong><br>
                👤 المدير: admin / admin123<br>
                👤 المعتمد: approver / approver123<br>
                👤 أمين الصندوق: cashier / cashier123<br>
                👤 المراجع: auditor / auditor123
            </div>
        </div>
    </div>
    {% endblock %}
    '''
    
    return render_template_string(login_html, HTML_TEMPLATE=HTML_TEMPLATE, 
                                 error=error, hide_header=True, title='تسجيل الدخول')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_audit(session['user_id'], 'تسجيل خروج')
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = get_db()
    c = conn.cursor()
    
    # Get statistics
    stats = {}
    
    # Total balances
    c.execute("SELECT COUNT(*) as count, SUM(opening_balance) as total FROM cashboxes WHERE is_active = 1")
    result = c.fetchone()
    stats['cashbox_count'] = result['count']
    stats['total_opening'] = result['total'] or 0
    
    # Today's transactions
    today = date.today().isoformat()
    c.execute("""SELECT 
                    COUNT(*) as count,
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                 FROM transactions 
                 WHERE DATE(txn_date) = ? AND status = 'approved'""", (today,))
    result = c.fetchone()
    stats['today_count'] = result['count']
    stats['today_income'] = result['income'] or 0
    stats['today_expense'] = result['expense'] or 0
    
    # Pending approvals
    c.execute("SELECT COUNT(*) as count FROM transactions WHERE status = 'draft'")
    stats['pending_count'] = c.fetchone()['count']
    
    # Get cashboxes with balances
    c.execute("SELECT * FROM cashboxes WHERE is_active = 1")
    cashboxes = []
    for box in c.fetchall():
        balance = get_cashbox_balance(box['id'])
        cashboxes.append({
            'id': box['id'],
            'code': box['code'],
            'name': box['name'],
            'currency': box['currency'],
            'balance': balance
        })
    
    # Get recent transactions
    c.execute("""SELECT t.*, c.name as cashbox_name, cat.name as category_name, p.name as partner_name
                 FROM transactions t
                 LEFT JOIN cashboxes c ON t.cashbox_id = c.id
                 LEFT JOIN categories cat ON t.category_id = cat.id
                 LEFT JOIN partners p ON t.partner_id = p.id
                 ORDER BY t.created_at DESC
                 LIMIT 10""")
    recent_transactions = c.fetchall()
    
    conn.close()
    
    dashboard_html = '''
    {% extends HTML_TEMPLATE %}
    {% block content %}
    <h2 style="margin-bottom: 30px;">لوحة التحكم</h2>
    
    <div class="stats-grid">
        <div class="stat-card primary">
            <h3>إجمالي الأرصدة</h3>
            <div class="value">{{ "{:,.0f}".format(stats.total_opening) }} <span class="unit">جنيه</span></div>
        </div>
        <div class="stat-card success">
            <h3>مقبوضات اليوم</h3>
            <div class="value">{{ "{:,.0f}".format(stats.today_income) }} <span class="unit">جنيه</span></div>
        </div>
        <div class="stat-card warning">
            <h3>مدفوعات اليوم</h3>
            <div class="value">{{ "{:,.0f}".format(stats.today_expense) }} <span class="unit">جنيه</span></div>
        </div>
        <div class="stat-card info">
            <h3>معاملات معلقة</h3>
            <div class="value">{{ stats.pending_count }} <span class="unit">معاملة</span></div>
        </div>
    </div>
    
    <div class="quick-actions">
        <a href="/transactions/new?type=receipt" class="quick-action">
            <div>💵</div>
            <div>سند قبض جديد</div>
        </a>
        <a href="/transactions/new?type=payment" class="quick-action">
            <div>💸</div>
            <div>سند صرف جديد</div>
        </a>
        <a href="/transfers" class="quick-action">
            <div>🔄</div>
            <div>تحويل بين الخزائن</div>
        </a>
        <a href="/reports/daily" class="quick-action">
            <div>📊</div>
            <div>تقرير اليوم</div>
        </a>
    </div>
    
    <div class="table-container">
        <div class="table-header">
            <span>📦 أرصدة الخزائن</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>الكود</th>
                    <th>اسم الخزنة</th>
                    <th>العملة</th>
                    <th>الرصيد الحالي</th>
                    <th>الحالة</th>
                </tr>
            </thead>
            <tbody>
                {% for box in cashboxes %}
                <tr>
                    <td><strong>{{ box.code }}</strong></td>
                    <td>{{ box.name }}</td>
                    <td>{{ box.currency }}</td>
                    <td><strong>{{ "{:,.2f}".format(box.balance) }}</strong></td>
                    <td><span class="badge success">نشط</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div class="table-container">
        <div class="table-header">
            <span>📋 آخر المعاملات</span>
            <a href="/transactions" class="btn btn-sm btn-primary">عرض الكل</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th>رقم السند</th>
                    <th>النوع</th>
                    <th>الخزنة</th>
                    <th>المبلغ</th>
                    <th>التصنيف</th>
                    <th>الشريك</th>
                    <th>الحالة</th>
                </tr>
            </thead>
            <tbody>
                {% for txn in recent_transactions %}
                <tr>
                    <td>{{ txn.voucher_no or '-' }}</td>
                    <td>
                        {% if txn.txn_type == 'receipt' %}
                            <span class="badge success">قبض</span>
                        {% elif txn.txn_type == 'payment' %}
                            <span class="badge danger">صرف</span>
                        {% else %}
                            <span class="badge info">تحويل</span>
                        {% endif %}
                    </td>
                    <td>{{ txn.cashbox_name }}</td>
                    <td><strong>{{ "{:,.2f}".format(txn.amount) }}</strong></td>
                    <td>{{ txn.category_name or '-' }}</td>
                    <td>{{ txn.partner_name or '-' }}</td>
                    <td>
                        {% if txn.status == 'approved' %}
                            <span class="badge success">معتمد</span>
                        {% elif txn.status == 'draft' %}
                            <span class="badge warning">مسودة</span>
                        {% else %}
                            <span class="badge danger">ملغي</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endblock %}
    '''
    
    return render_template_string(dashboard_html, HTML_TEMPLATE=HTML_TEMPLATE,
                                 stats=stats, cashboxes=cashboxes, 
                                 recent_transactions=recent_transactions,
                                 page='dashboard', title='لوحة التحكم')

@app.route('/transactions')
def transactions_list():
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = get_db()
    c = conn.cursor()
    
    # Build query with filters
    query = """SELECT t.*, c.name as cashbox_name, cat.name as category_name, 
                      p.name as partner_name, u.fullname as created_by_name
               FROM transactions t
               LEFT JOIN cashboxes c ON t.cashbox_id = c.id
               LEFT JOIN categories cat ON t.category_id = cat.id
               LEFT JOIN partners p ON t.partner_id = p.id
               LEFT JOIN users u ON t.created_by = u.id
               WHERE 1=1"""
    
    params = []
    
    # Apply filters
    search = request.args.get('search')
    if search:
        query += " AND (t.voucher_no LIKE ? OR t.description LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    status = request.args.get('status')
    if status:
        query += " AND t.status = ?"
        params.append(status)
    
    txn_type = request.args.get('type')
    if txn_type:
        query += " AND t.txn_type = ?"
        params.append(txn_type)
    
    query += " ORDER BY t.created_at DESC LIMIT 100"
    
    c.execute(query, params)
    transactions = c.fetchall()
    
    conn.close()
    
    transactions_html = '''
    {% extends HTML_TEMPLATE %}
    {% block content %}
    <h2 style="margin-bottom: 30px;">المعاملات</h2>
    
    <div class="search-bar">
        <form method="GET" style="display: flex; gap: 10px; width: 100%;">
            <input type="text" name="search" placeholder="بحث برقم السند أو الوصف..." 
                   class="form-control" value="{{ request.args.get('search', '') }}">
            <select name="type" class="form-control" style="width: 200px;">
                <option value="">كل الأنواع</option>
                <option value="receipt" {{ 'selected' if request.args.get('type') == 'receipt' }}>قبض</option>
                <option value="payment" {{ 'selected' if request.args.get('type') == 'payment' }}>صرف</option>
                <option value="transfer_in" {{ 'selected' if request.args.get('type') == 'transfer_in' }}>تحويل وارد</option>
                <option value="transfer_out" {{ 'selected' if request.args.get('type') == 'transfer_out' }}>تحويل صادر</option>
            </select>
            <select name="status" class="form-control" style="width: 200px;">
                <option value="">كل الحالات</option>
                <option value="draft" {{ 'selected' if request.args.get('status') == 'draft' }}>مسودة</option>
                <option value="approved" {{ 'selected' if request.args.get('status') == 'approved' }}>معتمد</option>
                <option value="void" {{ 'selected' if request.args.get('status') == 'void' }}>ملغي</option>
            </select>
            <button type="submit" class="btn btn-primary">بحث</button>
            <a href="/transactions/new" class="btn btn-success">معاملة جديدة</a>
        </form>
    </div>
    
    <div class="table-container">
        <div class="table-header">
            <span>📋 قائمة المعاملات</span>
        </div>
        <table>
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
                    <td>{{ txn.txn_date }}</td>
                    <td>
                        {% if txn.txn_type == 'receipt' %}
                            <span class="badge success">قبض</span>
                        {% elif txn.txn_type == 'payment' %}
                            <span class="badge danger">صرف</span>
                        {% elif txn.txn_type == 'transfer_in' %}
                            <span class="badge info">تحويل وارد</span>
                        {% else %}
                            <span class="badge warning">تحويل صادر</span>
                        {% endif %}
                    </td>
                    <td>{{ txn.cashbox_name }}</td>
                    <td><strong>{{ "{:,.2f}".format(txn.amount) }}</strong></td>
                    <td>{{ txn.category_name or '-' }}</td>
                    <td>{{ txn.partner_name or '-' }}</td>
                    <td>{{ txn.description[:50] if txn.description else '-' }}</td>
                    <td>
                        {% if txn.status == 'approved' %}
                            <span class="badge success">معتمد</span>
                        {% elif txn.status == 'draft' %}
                            <span class="badge warning">مسودة</span>
                        {% else %}
                            <span class="badge danger">ملغي</span>
                        {% endif %}
                    </td>
                    <td>{{ txn.created_by_name }}</td>
                    <td>
                        <div class="actions">
                            <a href="/transactions/{{ txn.id }}" class="btn btn-info btn-sm">عرض</a>
                            {% if txn.status == 'draft' and session.role in ['admin', 'approver'] %}
                            <form method="POST" action="/transactions/{{ txn.id }}/approve" style="display: inline;">
                                <button type="submit" class="btn btn-success btn-sm">اعتماد</button>
                            </form>
                            {% endif %}
                            {% if txn.status != 'void' and session.role in ['admin', 'approver'] %}
                            <form method="POST" action="/transactions/{{ txn.id }}/void" style="display: inline;">
                                <button type="submit" class="btn btn-danger btn-sm">إلغاء</button>
                            </form>
                            {% endif %}
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endblock %}
    '''
    
    return render_template_string(transactions_html, HTML_TEMPLATE=HTML_TEMPLATE,
                                 transactions=transactions, request=request,
                                 page='transactions', title='المعاملات')

@app.route('/transactions/new', methods=['GET', 'POST'])
def transaction_new():
    if 'user_id' not in session:
        return redirect('/login')
    
    if not check_permission(session['role'], 'create'):
        flash('ليس لديك صلاحية لإنشاء معاملات', 'danger')
        return redirect('/transactions')
    
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        # Create transaction
        txn_id = str(uuid.uuid4())
        cashbox_id = request.form.get('cashbox_id')
        txn_type = request.form.get('txn_type')
        
        voucher_no = generate_voucher_no(cashbox_id, txn_type)
        
        c.execute("""INSERT INTO transactions 
                     (id, voucher_no, cashbox_id, txn_type, txn_date, category_id, 
                      partner_id, description, amount, created_by)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (txn_id, voucher_no, cashbox_id, txn_type,
                   request.form.get('txn_date'), request.form.get('category_id') or None,
                   request.form.get('partner_id') or None, request.form.get('description'),
                   float(request.form.get('amount')), session['user_id']))
        
        conn.commit()
        
        log_audit(session['user_id'], 'إنشاء معاملة', 'transactions', txn_id,
                 None, {'voucher_no': voucher_no, 'amount': request.form.get('amount')})
        
        flash('تم إنشاء المعاملة بنجاح', 'success')
        conn.close()
        return redirect('/transactions')
    
    # Get form data
    c.execute("SELECT * FROM cashboxes WHERE is_active = 1")
    cashboxes = c.fetchall()
    
    c.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY kind, name")
    categories = c.fetchall()
    
    c.execute("SELECT * FROM partners WHERE is_active = 1 ORDER BY name")
    partners = c.fetchall()
    
    conn.close()
    
    default_type = request.args.get('type', 'receipt')
    
    form_html = '''
    {% extends HTML_TEMPLATE %}
    {% block content %}
    <div class="form-container">
        <h2>معاملة جديدة</h2>
        
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label>نوع المعاملة *</label>
                    <select name="txn_type" class="form-control" required>
                        <option value="receipt" {{ 'selected' if default_type == 'receipt' }}>سند قبض</option>
                        <option value="payment" {{ 'selected' if default_type == 'payment' }}>سند صرف</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>الخزنة *</label>
                    <select name="cashbox_id" class="form-control" required>
                        <option value="">اختر الخزنة...</option>
                        {% for box in cashboxes %}
                        <option value="{{ box.id }}">{{ box.name }} ({{ box.code }})</option>
                        {% endfor %}
                    </select>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>التاريخ *</label>
                    <input type="date" name="txn_date" class="form-control" 
                           value="{{ date.today() }}" required>
                </div>
                
                <div class="form-group">
                    <label>المبلغ *</label>
                    <input type="number" name="amount" class="form-control" 
                           step="0.01" min="0.01" required>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>التصنيف</label>
                    <select name="category_id" class="form-control">
                        <option value="">اختر التصنيف...</option>
                        {% for cat in categories %}
                        <option value="{{ cat.id }}">{{ cat.name }} ({{ cat.kind }})</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label>الشريك</label>
                    <select name="partner_id" class="form-control">
                        <option value="">اختر الشريك...</option>
                        {% for partner in partners %}
                        <option value="{{ partner.id }}">{{ partner.name }} ({{ partner.kind }})</option>
                        {% endfor %}
                    </select>
                </div>
            </div>
            
            <div class="form-group">
                <label>الوصف</label>
                <textarea name="description" class="form-control" rows="3"></textarea>
            </div>
            
            <div class="btn-group">
                <button type="submit" class="btn btn-primary">حفظ المعاملة</button>
                <a href="/transactions" class="btn btn-danger">إلغاء</a>
            </div>
        </form>
    </div>
    {% endblock %}
    '''
    
    return render_template_string(form_html, HTML_TEMPLATE=HTML_TEMPLATE,
                                 cashboxes=cashboxes, categories=categories,
                                 partners=partners, default_type=default_type,
                                 date=date, title='معاملة جديدة')

@app.route('/transactions/<txn_id>/approve', methods=['POST'])
def transaction_approve(txn_id):
    if 'user_id' not in session:
        return redirect('/login')
    
    if not check_permission(session['role'], 'approve'):
        flash('ليس لديك صلاحية لاعتماد المعاملات', 'danger')
        return redirect('/transactions')
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("UPDATE transactions SET status = 'approved', approved_by = ? WHERE id = ?",
              (session['user_id'], txn_id))
    conn.commit()
    
    log_audit(session['user_id'], 'اعتماد معاملة', 'transactions', txn_id)
    
    flash('تم اعتماد المعاملة بنجاح', 'success')
    conn.close()
    return redirect('/transactions')

@app.route('/transactions/<txn_id>/void', methods=['POST'])
def transaction_void(txn_id):
    if 'user_id' not in session:
        return redirect('/login')
    
    if not check_permission(session['role'], 'void'):
        flash('ليس لديك صلاحية لإلغاء المعاملات', 'danger')
        return redirect('/transactions')
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("UPDATE transactions SET status = 'void' WHERE id = ?", (txn_id,))
    conn.commit()
    
    log_audit(session['user_id'], 'إلغاء معاملة', 'transactions', txn_id)
    
    flash('تم إلغاء المعاملة', 'warning')
    conn.close()
    return redirect('/transactions')

@app.route('/cashboxes')
def cashboxes_list():
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM cashboxes WHERE is_active = 1")
    cashboxes = []
    for box in c.fetchall():
        balance = get_cashbox_balance(box['id'])
        
        # Get today's transactions
        today = date.today().isoformat()
        c.execute("""SELECT 
                        SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                        SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                     FROM transactions 
                     WHERE cashbox_id = ? AND DATE(txn_date) = ? AND status = 'approved'""", 
                  (box['id'], today))
        result = c.fetchone()
        
        cashboxes.append({
            'id': box['id'],
            'code': box['code'],
            'name': box['name'],
            'currency': box['currency'],
            'opening_balance': box['opening_balance'],
            'balance': balance,
            'today_income': result['income'] or 0,
            'today_expense': result['expense'] or 0
        })
    
    conn.close()
    
    cashboxes_html = '''
    {% extends HTML_TEMPLATE %}
    {% block content %}
    <h2 style="margin-bottom: 30px;">الخزائن</h2>
    
    {% if session.role == 'admin' %}
    <div style="margin-bottom: 20px;">
        <a href="/cashboxes/new" class="btn btn-success">إضافة خزنة جديدة</a>
    </div>
    {% endif %}
    
    <div class="stats-grid">
        {% for box in cashboxes %}
        <div class="stat-card">
            <h3>{{ box.name }} ({{ box.code }})</h3>
            <div class="value">{{ "{:,.2f}".format(box.balance) }} <span class="unit">{{ box.currency }}</span></div>
            <div style="margin-top: 15px; font-size: 14px;">
                <div>الرصيد الافتتاحي: {{ "{:,.2f}".format(box.opening_balance) }}</div>
                <div>مقبوضات اليوم: <span style="color: green;">+{{ "{:,.2f}".format(box.today_income) }}</span></div>
                <div>مدفوعات اليوم: <span style="color: red;">-{{ "{:,.2f}".format(box.today_expense) }}</span></div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% endblock %}
    '''
    
    return render_template_string(cashboxes_html, HTML_TEMPLATE=HTML_TEMPLATE,
                                 cashboxes=cashboxes, title='الخزائن')

@app.route('/reports/daily')
def report_daily():
    if 'user_id' not in session:
        return redirect('/login')
    
    report_date = request.args.get('date', date.today().isoformat())
    
    conn = get_db()
    c = conn.cursor()
    
    # Get transactions for the day
    c.execute("""SELECT t.*, c.name as cashbox_name, cat.name as category_name, 
                        p.name as partner_name
                 FROM transactions t
                 LEFT JOIN cashboxes c ON t.cashbox_id = c.id
                 LEFT JOIN categories cat ON t.category_id = cat.id
                 LEFT JOIN partners p ON t.partner_id = p.id
                 WHERE DATE(t.txn_date) = ? AND t.status = 'approved'
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
    
    report_html = '''
    {% extends HTML_TEMPLATE %}
    {% block content %}
    <h2>تقرير الحركة اليومية</h2>
    
    <div class="search-bar">
        <form method="GET">
            <input type="date" name="date" value="{{ report_date }}" class="form-control" style="width: 200px;">
            <button type="submit" class="btn btn-primary">عرض</button>
            <button type="button" class="btn btn-success" onclick="window.print()">طباعة</button>
        </form>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card success">
            <h3>إجمالي المقبوضات</h3>
            <div class="value">{{ "{:,.2f}".format(totals.receipt + totals.transfer_in) }}</div>
        </div>
        <div class="stat-card warning">
            <h3>إجمالي المدفوعات</h3>
            <div class="value">{{ "{:,.2f}".format(totals.payment + totals.transfer_out) }}</div>
        </div>
        <div class="stat-card primary">
            <h3>صافي اليوم</h3>
            <div class="value">{{ "{:,.2f}".format((totals.receipt + totals.transfer_in) - (totals.payment + totals.transfer_out)) }}</div>
        </div>
    </div>
    
    <div class="table-container">
        <div class="table-header">
            <span>تفاصيل المعاملات - {{ report_date }}</span>
        </div>
        <table>
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
                    <td>
                        {% if txn.txn_type in ['receipt', 'transfer_in'] %}
                        {{ "{:,.2f}".format(txn.amount) }}
                        {% else %}-{% endif %}
                    </td>
                    <td>
                        {% if txn.txn_type in ['payment', 'transfer_out'] %}
                        {{ "{:,.2f}".format(txn.amount) }}
                        {% else %}-{% endif %}
                    </td>
                </tr>
                {% endfor %}
                <tr style="font-weight: bold; background: #f8f9fa;">
                    <td colspan="6">الإجمالي</td>
                    <td>{{ "{:,.2f}".format(totals.receipt + totals.transfer_in) }}</td>
                    <td>{{ "{:,.2f}".format(totals.payment + totals.transfer_out) }}</td>
                </tr>
            </tbody>
        </table>
    </div>
    {% endblock %}
    '''
    
    return render_template_string(report_html, HTML_TEMPLATE=HTML_TEMPLATE,
                                 transactions=transactions, totals=totals,
                                 report_date=report_date, title='تقرير يومي')

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
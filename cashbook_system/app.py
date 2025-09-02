#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
import json
from datetime import datetime, date
import uuid
from flask import Flask, render_template_string, request, redirect, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'cashbook-professional-2024'

# Create directories
os.makedirs('instance', exist_ok=True)
os.makedirs('uploads', exist_ok=True)

# Database initialization
def init_db():
    """Initialize database with all tables"""
    conn = sqlite3.connect('instance/cashbook.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        fullname TEXT,
        role TEXT DEFAULT 'cashier',
        is_active INTEGER DEFAULT 1
    )''')
    
    # Cash boxes table
    c.execute('''CREATE TABLE IF NOT EXISTS cashboxes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        currency TEXT DEFAULT 'EGP',
        opening_balance REAL DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')
    
    # Partners table
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT DEFAULT 'other',
        phone TEXT,
        email TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    
    # Categories table
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
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
        created_by INTEGER NOT NULL,
        approved_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashboxes(id),
        FOREIGN KEY (category_id) REFERENCES categories(id),
        FOREIGN KEY (partner_id) REFERENCES partners(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
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

def generate_voucher_no(cashbox_id, txn_type):
    """Generate automatic voucher number"""
    conn = get_db()
    c = conn.cursor()
    
    # Get cashbox code
    c.execute("SELECT code FROM cashboxes WHERE id = ?", (cashbox_id,))
    cashbox = c.fetchone()
    if not cashbox:
        return None
    
    # Generate prefix
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

# HTML Template
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نظام إدارة الخزينة</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, 'Segoe UI', 'Arial', sans-serif; background: #f5f6fa; min-height: 100vh; }
        
        .header {
            background: white;
            padding: 15px 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .nav {
            background: #2c3e50;
            padding: 0;
        }
        
        .nav ul {
            list-style: none;
            display: flex;
            padding: 0 20px;
        }
        
        .nav a {
            display: block;
            padding: 15px 20px;
            color: white;
            text-decoration: none;
        }
        
        .nav a:hover { background: #34495e; }
        .nav .active { background: #3498db; }
        
        .container { padding: 30px; max-width: 1400px; margin: 0 auto; }
        
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
        
        tr:hover { background: #fafbfc; }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge.success { background: #d4edda; color: #155724; }
        .badge.warning { background: #fff3cd; color: #856404; }
        .badge.danger { background: #f8d7da; color: #721c24; }
        .badge.info { background: #d1ecf1; color: #0c5460; }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            color: white;
        }
        
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .btn-success { background: #28a745; }
        .btn-danger { background: #dc3545; }
        .btn-warning { background: #ffc107; color: #333; }
        .btn-info { background: #17a2b8; }
        .btn-sm { padding: 5px 10px; font-size: 12px; }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .form-container {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            max-width: 800px;
            margin: 0 auto;
        }
        
        .form-group { margin-bottom: 20px; }
        
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
        }
        
        .form-control:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
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
            border: 2px solid transparent;
        }
        
        .quick-action:hover {
            border-color: #667eea;
            transform: translateY(-3px);
        }
        
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
        
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .alert-danger {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
    </style>
</head>
<body>
    {{ content | safe }}
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
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['fullname'] = user['fullname']
            session['role'] = user['role']
            return redirect('/dashboard')
        
        error = 'خطأ في اسم المستخدم أو كلمة المرور'
    
    content = f'''
    <div class="login-container">
        <div class="login-box">
            <h2 style="text-align: center; margin-bottom: 30px;">🏦 نظام إدارة الخزينة</h2>
            {'<div class="alert alert-danger">' + error + '</div>' if error else ''}
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
                <strong>بيانات الدخول:</strong><br>
                👤 المدير: admin / admin123<br>
                👤 المعتمد: approver / approver123<br>
                👤 أمين الصندوق: cashier / cashier123<br>
                👤 المراجع: auditor / auditor123
            </div>
        </div>
    </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, content=content)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = get_db()
    c = conn.cursor()
    
    # Get statistics
    today = date.today().isoformat()
    
    # Total balances
    c.execute("SELECT COUNT(*) as count FROM cashboxes WHERE is_active = 1")
    cashbox_count = c.fetchone()['count']
    
    # Today's transactions
    c.execute("""SELECT 
                    COUNT(*) as count,
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                 FROM transactions 
                 WHERE DATE(txn_date) = ? AND status = 'approved'""", (today,))
    result = c.fetchone()
    today_income = result['income'] or 0
    today_expense = result['expense'] or 0
    
    # Pending approvals
    c.execute("SELECT COUNT(*) as count FROM transactions WHERE status = 'draft'")
    pending_count = c.fetchone()['count']
    
    # Get cashboxes with balances
    c.execute("SELECT * FROM cashboxes WHERE is_active = 1")
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
                 FROM transactions t
                 LEFT JOIN cashboxes c ON t.cashbox_id = c.id
                 ORDER BY t.created_at DESC
                 LIMIT 5""")
    transactions = c.fetchall()
    
    conn.close()
    
    # Build HTML
    nav_html = f'''
    <div class="header">
        <h1>💰 نظام إدارة الخزينة</h1>
        <div>
            <span>{session.get('fullname')} ({session.get('role')})</span>
            <a href="/logout" class="btn btn-danger btn-sm">خروج</a>
        </div>
    </div>
    
    <nav class="nav">
        <ul>
            <li><a href="/dashboard" class="active">الرئيسية</a></li>
            <li><a href="/transactions">المعاملات</a></li>
            <li><a href="/cashboxes">الخزائن</a></li>
            <li><a href="/reports">التقارير</a></li>
        </ul>
    </nav>
    '''
    
    content = nav_html + f'''
    <div class="container">
        <h2 style="margin-bottom: 30px;">لوحة التحكم</h2>
        
        <div class="stats-grid">
            <div class="stat-card primary">
                <h3>عدد الخزائن</h3>
                <div class="value">{cashbox_count}</div>
            </div>
            <div class="stat-card success">
                <h3>مقبوضات اليوم</h3>
                <div class="value">{today_income:,.0f} جنيه</div>
            </div>
            <div class="stat-card warning">
                <h3>مدفوعات اليوم</h3>
                <div class="value">{today_expense:,.0f} جنيه</div>
            </div>
            <div class="stat-card info">
                <h3>معاملات معلقة</h3>
                <div class="value">{pending_count}</div>
            </div>
        </div>
        
        <div class="quick-actions">
            <a href="/transactions/new?type=receipt" class="quick-action">
                <div style="font-size: 36px;">💵</div>
                <div>سند قبض جديد</div>
            </a>
            <a href="/transactions/new?type=payment" class="quick-action">
                <div style="font-size: 36px;">💸</div>
                <div>سند صرف جديد</div>
            </a>
            <a href="/transfers" class="quick-action">
                <div style="font-size: 36px;">🔄</div>
                <div>تحويل بين الخزائن</div>
            </a>
            <a href="/reports" class="quick-action">
                <div style="font-size: 36px;">📊</div>
                <div>التقارير</div>
            </a>
        </div>
        
        <div class="table-container">
            <div class="table-header">أرصدة الخزائن</div>
            <table>
                <thead>
                    <tr>
                        <th>الكود</th>
                        <th>اسم الخزنة</th>
                        <th>العملة</th>
                        <th>الرصيد الحالي</th>
                    </tr>
                </thead>
                <tbody>
    '''
    
    for box in cashboxes:
        content += f'''
                    <tr>
                        <td><strong>{box['code']}</strong></td>
                        <td>{box['name']}</td>
                        <td>{box['currency']}</td>
                        <td><strong>{box['balance']:,.2f}</strong></td>
                    </tr>
        '''
    
    content += '''
                </tbody>
            </table>
        </div>
    </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, content=content)

@app.route('/transactions')
def transactions_list():
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""SELECT t.*, c.name as cashbox_name
                 FROM transactions t
                 LEFT JOIN cashboxes c ON t.cashbox_id = c.id
                 ORDER BY t.created_at DESC
                 LIMIT 50""")
    transactions = c.fetchall()
    conn.close()
    
    nav_html = f'''
    <div class="header">
        <h1>💰 نظام إدارة الخزينة</h1>
        <div>
            <span>{session.get('fullname')} ({session.get('role')})</span>
            <a href="/logout" class="btn btn-danger btn-sm">خروج</a>
        </div>
    </div>
    
    <nav class="nav">
        <ul>
            <li><a href="/dashboard">الرئيسية</a></li>
            <li><a href="/transactions" class="active">المعاملات</a></li>
            <li><a href="/cashboxes">الخزائن</a></li>
            <li><a href="/reports">التقارير</a></li>
        </ul>
    </nav>
    '''
    
    content = nav_html + '''
    <div class="container">
        <h2 style="margin-bottom: 30px;">المعاملات</h2>
        
        <div style="margin-bottom: 20px;">
            <a href="/transactions/new" class="btn btn-success">معاملة جديدة</a>
        </div>
        
        <div class="table-container">
            <div class="table-header">قائمة المعاملات</div>
            <table>
                <thead>
                    <tr>
                        <th>رقم السند</th>
                        <th>التاريخ</th>
                        <th>النوع</th>
                        <th>الخزنة</th>
                        <th>المبلغ</th>
                        <th>الحالة</th>
                        <th>إجراءات</th>
                    </tr>
                </thead>
                <tbody>
    '''
    
    for txn in transactions:
        type_badge = {
            'receipt': '<span class="badge success">قبض</span>',
            'payment': '<span class="badge danger">صرف</span>',
            'transfer_in': '<span class="badge info">تحويل وارد</span>',
            'transfer_out': '<span class="badge warning">تحويل صادر</span>'
        }.get(txn['txn_type'], txn['txn_type'])
        
        status_badge = {
            'approved': '<span class="badge success">معتمد</span>',
            'draft': '<span class="badge warning">مسودة</span>',
            'void': '<span class="badge danger">ملغي</span>'
        }.get(txn['status'], txn['status'])
        
        content += f'''
                    <tr>
                        <td><strong>{txn['voucher_no'] or '-'}</strong></td>
                        <td>{txn['txn_date']}</td>
                        <td>{type_badge}</td>
                        <td>{txn['cashbox_name']}</td>
                        <td><strong>{txn['amount']:,.2f}</strong></td>
                        <td>{status_badge}</td>
                        <td>
        '''
        
        if txn['status'] == 'draft' and session.get('role') in ['admin', 'approver']:
            content += f'''
                            <form method="POST" action="/transactions/{txn['id']}/approve" style="display: inline;">
                                <button type="submit" class="btn btn-success btn-sm">اعتماد</button>
                            </form>
            '''
        
        content += '''
                        </td>
                    </tr>
        '''
    
    content += '''
                </tbody>
            </table>
        </div>
    </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, content=content)

@app.route('/transactions/new', methods=['GET', 'POST'])
def transaction_new():
    if 'user_id' not in session:
        return redirect('/login')
    
    message = None
    
    if request.method == 'POST':
        conn = get_db()
        c = conn.cursor()
        
        txn_id = str(uuid.uuid4())
        cashbox_id = request.form.get('cashbox_id')
        txn_type = request.form.get('txn_type')
        voucher_no = generate_voucher_no(cashbox_id, txn_type)
        
        c.execute("""INSERT INTO transactions 
                     (id, voucher_no, cashbox_id, txn_type, txn_date, 
                      category_id, partner_id, description, amount, created_by)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (txn_id, voucher_no, cashbox_id, txn_type,
                   request.form.get('txn_date'),
                   request.form.get('category_id') or None,
                   request.form.get('partner_id') or None,
                   request.form.get('description'),
                   float(request.form.get('amount')),
                   session['user_id']))
        
        conn.commit()
        conn.close()
        
        return redirect('/transactions')
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM cashboxes WHERE is_active = 1")
    cashboxes = c.fetchall()
    
    c.execute("SELECT * FROM categories WHERE is_active = 1")
    categories = c.fetchall()
    
    c.execute("SELECT * FROM partners WHERE is_active = 1")
    partners = c.fetchall()
    
    conn.close()
    
    nav_html = f'''
    <div class="header">
        <h1>💰 نظام إدارة الخزينة</h1>
        <div>
            <span>{session.get('fullname')} ({session.get('role')})</span>
            <a href="/logout" class="btn btn-danger btn-sm">خروج</a>
        </div>
    </div>
    
    <nav class="nav">
        <ul>
            <li><a href="/dashboard">الرئيسية</a></li>
            <li><a href="/transactions" class="active">المعاملات</a></li>
            <li><a href="/cashboxes">الخزائن</a></li>
            <li><a href="/reports">التقارير</a></li>
        </ul>
    </nav>
    '''
    
    content = nav_html + f'''
    <div class="container">
        <div class="form-container">
            <h2>معاملة جديدة</h2>
            
            <form method="POST">
                <div class="form-row">
                    <div class="form-group">
                        <label>نوع المعاملة *</label>
                        <select name="txn_type" class="form-control" required>
                            <option value="receipt">سند قبض</option>
                            <option value="payment">سند صرف</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>الخزنة *</label>
                        <select name="cashbox_id" class="form-control" required>
                            <option value="">اختر الخزنة...</option>
    '''
    
    for box in cashboxes:
        content += f'<option value="{box["id"]}">{box["name"]} ({box["code"]})</option>'
    
    content += f'''
                        </select>
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>التاريخ *</label>
                        <input type="date" name="txn_date" class="form-control" 
                               value="{date.today()}" required>
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
    '''
    
    for cat in categories:
        content += f'<option value="{cat["id"]}">{cat["name"]} ({cat["kind"]})</option>'
    
    content += '''
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>الشريك</label>
                        <select name="partner_id" class="form-control">
                            <option value="">اختر الشريك...</option>
    '''
    
    for partner in partners:
        content += f'<option value="{partner["id"]}">{partner["name"]} ({partner["kind"]})</option>'
    
    content += '''
                        </select>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>الوصف</label>
                    <textarea name="description" class="form-control" rows="3"></textarea>
                </div>
                
                <div style="display: flex; gap: 10px;">
                    <button type="submit" class="btn btn-primary">حفظ المعاملة</button>
                    <a href="/transactions" class="btn btn-danger">إلغاء</a>
                </div>
            </form>
        </div>
    </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, content=content)

@app.route('/transactions/<txn_id>/approve', methods=['POST'])
def transaction_approve(txn_id):
    if 'user_id' not in session:
        return redirect('/login')
    
    if session.get('role') not in ['admin', 'approver']:
        return redirect('/transactions')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE transactions SET status = 'approved', approved_by = ? WHERE id = ?",
              (session['user_id'], txn_id))
    conn.commit()
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
        cashboxes.append({
            'code': box['code'],
            'name': box['name'],
            'currency': box['currency'],
            'opening_balance': box['opening_balance'],
            'balance': balance
        })
    
    conn.close()
    
    nav_html = f'''
    <div class="header">
        <h1>💰 نظام إدارة الخزينة</h1>
        <div>
            <span>{session.get('fullname')} ({session.get('role')})</span>
            <a href="/logout" class="btn btn-danger btn-sm">خروج</a>
        </div>
    </div>
    
    <nav class="nav">
        <ul>
            <li><a href="/dashboard">الرئيسية</a></li>
            <li><a href="/transactions">المعاملات</a></li>
            <li><a href="/cashboxes" class="active">الخزائن</a></li>
            <li><a href="/reports">التقارير</a></li>
        </ul>
    </nav>
    '''
    
    content = nav_html + '''
    <div class="container">
        <h2 style="margin-bottom: 30px;">الخزائن</h2>
        
        <div class="stats-grid">
    '''
    
    for box in cashboxes:
        content += f'''
            <div class="stat-card">
                <h3>{box['name']} ({box['code']})</h3>
                <div class="value">{box['balance']:,.2f} <span style="font-size: 14px;">{box['currency']}</span></div>
                <div style="margin-top: 15px; font-size: 14px;">
                    <div>الرصيد الافتتاحي: {box['opening_balance']:,.2f}</div>
                </div>
            </div>
        '''
    
    content += '''
        </div>
    </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, content=content)

@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect('/login')
    
    nav_html = f'''
    <div class="header">
        <h1>💰 نظام إدارة الخزينة</h1>
        <div>
            <span>{session.get('fullname')} ({session.get('role')})</span>
            <a href="/logout" class="btn btn-danger btn-sm">خروج</a>
        </div>
    </div>
    
    <nav class="nav">
        <ul>
            <li><a href="/dashboard">الرئيسية</a></li>
            <li><a href="/transactions">المعاملات</a></li>
            <li><a href="/cashboxes">الخزائن</a></li>
            <li><a href="/reports" class="active">التقارير</a></li>
        </ul>
    </nav>
    '''
    
    content = nav_html + '''
    <div class="container">
        <h2 style="margin-bottom: 30px;">التقارير</h2>
        
        <div class="quick-actions">
            <a href="/reports/daily" class="quick-action">
                <div style="font-size: 36px;">📅</div>
                <div>تقرير يومي</div>
            </a>
            <a href="/reports/cashbox" class="quick-action">
                <div style="font-size: 36px;">💰</div>
                <div>أرصدة الخزائن</div>
            </a>
            <a href="/reports/category" class="quick-action">
                <div style="font-size: 36px;">🏷️</div>
                <div>حسب التصنيف</div>
            </a>
            <a href="/reports/partner" class="quick-action">
                <div style="font-size: 36px;">👥</div>
                <div>حسب الشريك</div>
            </a>
        </div>
    </div>
    '''
    
    return render_template_string(BASE_TEMPLATE, content=content)

@app.route('/transfers')
def transfers():
    return redirect('/transactions')

# Health check for Render
@app.route('/health')
def health():
    return 'OK'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
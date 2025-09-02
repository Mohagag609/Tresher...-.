#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🏦 نظام إدارة الخزينة الاحترافي
Professional Cash Management System
Version: 2.0
"""

import os
import sqlite3
import uuid
import json
from decimal import Decimal
from datetime import datetime, date, timedelta
from flask import Flask, render_template_string, request, redirect, session, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import io
import csv

# ==================== التكوين الأساسي ====================
app = Flask(__name__)
app.secret_key = 'professional-cashbook-system-2024-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file

# إنشاء المجلدات المطلوبة
os.makedirs('instance', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('reports', exist_ok=True)

# ==================== قاعدة البيانات ====================
def init_database():
    """إنشاء قاعدة البيانات بالهيكل المطلوب بالضبط"""
    conn = sqlite3.connect('instance/cashbook.db')
    c = conn.cursor()
    
    # تفعيل Foreign Keys
    c.execute("PRAGMA foreign_keys = ON")
    
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        full_name VARCHAR(100),
        email VARCHAR(100),
        role VARCHAR(20) DEFAULT 'cashier',
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )''')
    
    # جدول الخزائن - CashBox
    c.execute('''CREATE TABLE IF NOT EXISTS cashboxes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code VARCHAR(10) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        currency VARCHAR(3) DEFAULT 'EGP',
        opening_balance DECIMAL(12,2) DEFAULT 0.00,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # جدول الشركاء - Partner
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(150) NOT NULL,
        kind VARCHAR(10) DEFAULT 'other' CHECK(kind IN ('customer', 'supplier', 'other')),
        phone VARCHAR(30),
        email VARCHAR(100),
        address TEXT,
        tax_id VARCHAR(50),
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # جدول التصنيفات - Category
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(120) NOT NULL,
        kind VARCHAR(10) NOT NULL CHECK(kind IN ('income', 'expense', 'transfer')),
        parent_id INTEGER,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
    )''')
    
    # جدول المعاملات - CashTransaction
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
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
        created_by INTEGER NOT NULL,
        approved_by INTEGER,
        linked_txn_id VARCHAR(36),
        attachment VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashboxes(id) ON DELETE RESTRICT,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
        FOREIGN KEY (partner_id) REFERENCES partners(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
        FOREIGN KEY (approved_by) REFERENCES users(id),
        FOREIGN KEY (linked_txn_id) REFERENCES transactions(id) ON DELETE SET NULL
    )''')
    
    # جدول إغلاق الفترات - PeriodClose
    c.execute('''CREATE TABLE IF NOT EXISTS period_closes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cashbox_id INTEGER NOT NULL,
        month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
        year INTEGER NOT NULL,
        closed_by INTEGER NOT NULL,
        closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cashbox_id) REFERENCES cashboxes(id) ON DELETE RESTRICT,
        FOREIGN KEY (closed_by) REFERENCES users(id) ON DELETE RESTRICT,
        UNIQUE(cashbox_id, month, year)
    )''')
    
    # جدول سجل المراجعة - Audit Log
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action VARCHAR(100) NOT NULL,
        table_name VARCHAR(50),
        record_id VARCHAR(50),
        old_values TEXT,
        new_values TEXT,
        ip_address VARCHAR(45),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # إنشاء الفهارس للأداء
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_status ON transactions(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_cashbox ON transactions(cashbox_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
    
    # إضافة البيانات الافتراضية
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        # المستخدمون الافتراضيون
        users = [
            ('admin', generate_password_hash('admin123'), 'مدير النظام', 'admin@cashbook.com', 'admin'),
            ('approver', generate_password_hash('approver123'), 'المعتمد', 'approver@cashbook.com', 'approver'),
            ('cashier', generate_password_hash('cashier123'), 'أمين الصندوق', 'cashier@cashbook.com', 'cashier'),
            ('auditor', generate_password_hash('auditor123'), 'المراجع', 'auditor@cashbook.com', 'auditor')
        ]
        c.executemany("INSERT INTO users (username, password, full_name, email, role) VALUES (?, ?, ?, ?, ?)", users)
        
        # الخزائن الافتراضية
        cashboxes = [
            ('MAIN', 'الخزنة الرئيسية', 'EGP', 100000.00),
            ('PETTY', 'العهدة النثرية', 'EGP', 10000.00),
            ('BANK', 'الحساب البنكي', 'EGP', 500000.00),
            ('BRANCH1', 'خزنة الفرع الأول', 'EGP', 50000.00),
            ('BRANCH2', 'خزنة الفرع الثاني', 'EGP', 30000.00)
        ]
        c.executemany("INSERT INTO cashboxes (code, name, currency, opening_balance) VALUES (?, ?, ?, ?)", cashboxes)
        
        # التصنيفات الافتراضية
        categories = [
            # إيرادات
            ('مبيعات نقدية', 'income'),
            ('مبيعات آجلة', 'income'),
            ('خدمات استشارية', 'income'),
            ('عمولات', 'income'),
            ('إيرادات أخرى', 'income'),
            # مصروفات
            ('رواتب وأجور', 'expense'),
            ('إيجار', 'expense'),
            ('كهرباء ومياه', 'expense'),
            ('مصروفات إدارية', 'expense'),
            ('مشتريات', 'expense'),
            ('صيانة', 'expense'),
            ('دعاية وإعلان', 'expense'),
            ('مصروفات أخرى', 'expense'),
            # تحويلات
            ('تحويلات بين الخزائن', 'transfer')
        ]
        c.executemany("INSERT INTO categories (name, kind) VALUES (?, ?)", categories)
        
        # الشركاء الافتراضيون
        partners = [
            ('عميل نقدي', 'customer', '01000000000', 'cash@customer.com', 'القاهرة', ''),
            ('شركة الأمل للتجارة', 'customer', '01234567890', 'amal@company.com', 'القاهرة - مصر الجديدة', '123456789'),
            ('مؤسسة النور', 'customer', '01098765432', 'nour@foundation.org', 'الإسكندرية', '987654321'),
            ('شركة التوريدات المتحدة', 'supplier', '01111111111', 'united@supplies.com', 'القاهرة - وسط البلد', '456789123'),
            ('مورد قطع الغيار', 'supplier', '01222222222', 'parts@supplier.com', 'الجيزة', '789123456'),
            ('شركة الكهرباء', 'supplier', '19999', '', 'مصر', ''),
            ('موظف - أحمد محمد', 'other', '01555555555', 'ahmed@employee.com', 'القاهرة', '')
        ]
        c.executemany("INSERT INTO partners (name, kind, phone, email, address, tax_id) VALUES (?, ?, ?, ?, ?, ?)", partners)
    
    conn.commit()
    conn.close()

# تهيئة قاعدة البيانات عند بدء التطبيق
init_database()

# ==================== الدوال المساعدة ====================
def get_db():
    """الاتصال بقاعدة البيانات"""
    conn = sqlite3.connect('instance/cashbook.db')
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def login_required(f):
    """التحقق من تسجيل الدخول"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def check_permission(role_required):
    """التحقق من الصلاحيات"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect('/login')
            
            user_role = session.get('role', 'cashier')
            
            # Admin له كل الصلاحيات
            if user_role == 'admin':
                return f(*args, **kwargs)
            
            # التحقق من الصلاحيات حسب الدور
            permissions = {
                'approver': ['view', 'create', 'approve', 'void'],
                'cashier': ['view', 'create'],
                'auditor': ['view', 'reports']
            }
            
            if role_required in permissions.get(user_role, []):
                return f(*args, **kwargs)
            
            return jsonify({'error': 'ليس لديك صلاحية'}), 403
            
        return decorated_function
    return decorator

def log_audit(action, table_name=None, record_id=None, old_values=None, new_values=None):
    """تسجيل في سجل المراجعة"""
    if 'user_id' not in session:
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values, ip_address)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (session['user_id'], action, table_name, record_id,
               json.dumps(old_values) if old_values else None,
               json.dumps(new_values) if new_values else None,
               request.remote_addr))
    conn.commit()
    conn.close()

def generate_voucher_no(cashbox_id, txn_type):
    """توليد رقم السند التلقائي"""
    conn = get_db()
    c = conn.cursor()
    
    # الحصول على كود الخزنة
    c.execute("SELECT code FROM cashboxes WHERE id = ?", (cashbox_id,))
    cashbox = c.fetchone()
    if not cashbox:
        conn.close()
        return None
    
    year = datetime.now().year
    prefix = f"{cashbox['code']}-{year}"
    
    # الحصول على آخر رقم
    c.execute("SELECT voucher_no FROM transactions WHERE voucher_no LIKE ? ORDER BY voucher_no DESC LIMIT 1",
              (f"{prefix}-%",))
    last = c.fetchone()
    
    if last:
        seq = int(last['voucher_no'].split('-')[-1]) + 1
    else:
        seq = 1
    
    conn.close()
    return f"{prefix}-{seq:06d}"

def calculate_balance(cashbox_id):
    """حساب رصيد الخزنة"""
    conn = get_db()
    c = conn.cursor()
    
    # الرصيد الافتتاحي
    c.execute("SELECT opening_balance FROM cashboxes WHERE id = ?", (cashbox_id,))
    result = c.fetchone()
    if not result:
        conn.close()
        return 0
    
    opening = float(result['opening_balance'])
    
    # المعاملات المعتمدة
    c.execute("""SELECT 
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                 FROM transactions 
                 WHERE cashbox_id = ? AND status = 'approved'""", (cashbox_id,))
    result = c.fetchone()
    
    income = float(result['income'] or 0)
    expense = float(result['expense'] or 0)
    
    conn.close()
    return opening + income - expense

def create_transfer(from_box, to_box, amount, user_id, description=""):
    """إنشاء تحويل بين خزنتين"""
    conn = get_db()
    c = conn.cursor()
    
    try:
        # بدء المعاملة
        conn.execute("BEGIN TRANSACTION")
        
        # الحصول على تصنيف التحويل
        c.execute("SELECT id FROM categories WHERE kind = 'transfer' LIMIT 1")
        category = c.fetchone()
        category_id = category['id'] if category else None
        
        # إنشاء معاملة الصرف
        out_id = str(uuid.uuid4())
        out_voucher = generate_voucher_no(from_box, 'transfer_out')
        
        c.execute("""INSERT INTO transactions 
                    (id, cashbox_id, txn_type, status, date, category_id, description, amount, voucher_no, created_by, approved_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (out_id, from_box, 'transfer_out', 'approved', date.today(), category_id, 
                   description, amount, out_voucher, user_id, user_id))
        
        # إنشاء معاملة القبض
        in_id = str(uuid.uuid4())
        in_voucher = generate_voucher_no(to_box, 'transfer_in')
        
        c.execute("""INSERT INTO transactions 
                    (id, cashbox_id, txn_type, status, date, category_id, description, amount, voucher_no, created_by, approved_by, linked_txn_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (in_id, to_box, 'transfer_in', 'approved', date.today(), category_id,
                   f"تحويل من خزنة: {description}", amount, in_voucher, user_id, user_id, out_id))
        
        # تحديث معاملة الصرف بالربط
        c.execute("UPDATE transactions SET linked_txn_id = ? WHERE id = ?", (in_id, out_id))
        
        conn.commit()
        log_audit('إنشاء تحويل', 'transactions', f"{out_id},{in_id}", None, {'amount': amount})
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"Transfer error: {e}")
        return False
    finally:
        conn.close()

# ==================== القالب الرئيسي ====================
MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - نظام إدارة الخزينة الاحترافي</title>
    
    <!-- Bootstrap 5 RTL -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css">
    
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700&display=swap" rel="stylesheet">
    
    <!-- Animate.css -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">
    
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3f37c9;
            --success-color: #06ffa5;
            --danger-color: #ff006e;
            --warning-color: #ffbe0b;
            --info-color: #00b4d8;
            --dark-color: #0a0e27;
            --light-color: #f8f9fa;
            --sidebar-width: 280px;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Cairo', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--primary-color);
            border-radius: 5px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--secondary-color);
        }
        
        /* Login Page */
        .login-page {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            position: relative;
            overflow: hidden;
        }
        
        .login-page::before {
            content: '';
            position: absolute;
            width: 200%;
            height: 200%;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320"><path fill="%23ffffff" fill-opacity="0.1" d="M0,96L48,112C96,128,192,160,288,160C384,160,480,128,576,122.7C672,117,768,139,864,138.7C960,139,1056,117,1152,112C1248,107,1344,117,1392,122.7L1440,128L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"></path></svg>') no-repeat;
            animation: wave 10s linear infinite;
        }
        
        @keyframes wave {
            0% { transform: translateX(0); }
            100% { transform: translateX(-50%); }
        }
        
        .login-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 40px;
            width: 100%;
            max-width: 450px;
            position: relative;
            z-index: 1;
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .login-header h1 {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 10px;
        }
        
        .login-header p {
            color: #666;
            font-size: 0.9rem;
        }
        
        /* Navbar */
        .main-navbar {
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            padding: 0.75rem 0;
        }
        
        .navbar-brand {
            font-weight: 700;
            font-size: 1.5rem;
            color: white !important;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .navbar-brand i {
            font-size: 1.8rem;
        }
        
        .user-menu {
            display: flex;
            align-items: center;
            gap: 20px;
            color: white;
        }
        
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: white;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--primary-color);
            font-weight: 700;
        }
        
        /* Sidebar */
        .sidebar {
            position: fixed;
            top: 70px;
            right: 0;
            width: var(--sidebar-width);
            height: calc(100vh - 70px);
            background: linear-gradient(180deg, #1a1a2e 0%, #0f0f1e 100%);
            box-shadow: -2px 0 10px rgba(0, 0, 0, 0.1);
            overflow-y: auto;
            transition: all 0.3s ease;
            z-index: 100;
        }
        
        .sidebar-menu {
            padding: 20px 0;
        }
        
        .sidebar-item {
            margin-bottom: 5px;
        }
        
        .sidebar-link {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 15px 25px;
            color: rgba(255, 255, 255, 0.7);
            text-decoration: none;
            transition: all 0.3s ease;
            position: relative;
        }
        
        .sidebar-link:hover {
            color: white;
            background: rgba(255, 255, 255, 0.1);
        }
        
        .sidebar-link.active {
            color: white;
            background: var(--primary-color);
        }
        
        .sidebar-link.active::before {
            content: '';
            position: absolute;
            right: 0;
            top: 0;
            width: 4px;
            height: 100%;
            background: var(--success-color);
        }
        
        .sidebar-link i {
            font-size: 1.2rem;
            width: 25px;
            text-align: center;
        }
        
        /* Main Content */
        .main-content {
            margin-right: var(--sidebar-width);
            padding: 20px;
            min-height: calc(100vh - 70px);
            background: #f0f2f5;
            margin-top: 70px;
        }
        
        /* Cards */
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.08);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, transparent, rgba(255, 255, 255, 0.1));
            border-radius: 50%;
            transform: translate(30px, -30px);
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
        }
        
        .stat-card.primary {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
        }
        
        .stat-card.success {
            background: linear-gradient(135deg, #06ffa5, #00d084);
            color: white;
        }
        
        .stat-card.danger {
            background: linear-gradient(135deg, #ff006e, #c9184a);
            color: white;
        }
        
        .stat-card.warning {
            background: linear-gradient(135deg, #ffbe0b, #fb8500);
            color: white;
        }
        
        .stat-icon {
            font-size: 3rem;
            opacity: 0.3;
            position: absolute;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        
        /* Tables */
        .data-table {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.08);
        }
        
        .table-header {
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .table-header h3 {
            margin: 0;
            font-size: 1.3rem;
        }
        
        .table {
            margin: 0;
        }
        
        .table thead th {
            background: #f8f9fa;
            border: none;
            padding: 15px;
            font-weight: 600;
            color: #495057;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
        }
        
        .table tbody td {
            padding: 15px;
            vertical-align: middle;
            border-top: 1px solid #f0f0f0;
        }
        
        .table tbody tr:hover {
            background: #f8f9fa;
        }
        
        /* Badges */
        .badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.8rem;
        }
        
        /* Buttons */
        .btn-modern {
            padding: 10px 25px;
            border-radius: 10px;
            font-weight: 600;
            transition: all 0.3s ease;
            border: none;
            position: relative;
            overflow: hidden;
        }
        
        .btn-modern::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }
        
        .btn-modern:hover::before {
            width: 300px;
            height: 300px;
        }
        
        /* Forms */
        .form-modern .form-label {
            font-weight: 600;
            color: #495057;
            margin-bottom: 8px;
        }
        
        .form-modern .form-control,
        .form-modern .form-select {
            border-radius: 10px;
            border: 2px solid #e0e0e0;
            padding: 12px 15px;
            transition: all 0.3s ease;
        }
        
        .form-modern .form-control:focus,
        .form-modern .form-select:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 0.2rem rgba(67, 97, 238, 0.25);
        }
        
        /* Animations */
        .animate-in {
            animation: slideIn 0.5s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .sidebar {
                transform: translateX(100%);
            }
            
            .sidebar.active {
                transform: translateX(0);
            }
            
            .main-content {
                margin-right: 0;
            }
        }
        
        /* Loading Spinner */
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid var(--primary-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* Sweet Alert Override */
        .swal2-popup {
            border-radius: 15px !important;
        }
        
        /* Charts Container */
        .chart-container {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.08);
        }
    </style>
</head>
<body>
    {{ content|safe }}
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Sweet Alert -->
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    
    <!-- Custom JS -->
    <script>
        // تفعيل Tooltips
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl)
        });
        
        // دالة لعرض رسائل النجاح
        function showSuccess(message) {
            Swal.fire({
                icon: 'success',
                title: 'نجح',
                text: message,
                timer: 2000,
                showConfirmButton: false
            });
        }
        
        // دالة لعرض رسائل الخطأ
        function showError(message) {
            Swal.fire({
                icon: 'error',
                title: 'خطأ',
                text: message
            });
        }
        
        // دالة للتأكيد
        function confirmAction(message, callback) {
            Swal.fire({
                title: 'هل أنت متأكد؟',
                text: message,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#4361ee',
                cancelButtonColor: '#ff006e',
                confirmButtonText: 'نعم',
                cancelButtonText: 'إلغاء'
            }).then((result) => {
                if (result.isConfirmed) {
                    callback();
                }
            });
        }
    </script>
</body>
</html>
'''

# ==================== المسارات ====================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/login')

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
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            
            # تحديث آخر تسجيل دخول
            c.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
            conn.commit()
            
            log_audit('تسجيل دخول', 'users', user['id'])
            conn.close()
            
            return redirect('/dashboard')
        
        conn.close()
        error = 'خطأ في اسم المستخدم أو كلمة المرور'
    
    content = f'''
    <div class="login-page">
        <div class="login-card animate__animated animate__fadeInUp">
            <div class="login-header">
                <i class="fas fa-cash-register fa-3x mb-3" style="color: var(--primary-color);"></i>
                <h1>نظام إدارة الخزينة</h1>
                <p>النظام الاحترافي لإدارة المعاملات المالية</p>
            </div>
            
            {'<div class="alert alert-danger animate__animated animate__shakeX">' + error + '</div>' if error else ''}
            
            <form method="POST" class="form-modern">
                <div class="mb-3">
                    <label class="form-label">
                        <i class="fas fa-user"></i> اسم المستخدم
                    </label>
                    <input type="text" name="username" class="form-control" required autofocus>
                </div>
                
                <div class="mb-4">
                    <label class="form-label">
                        <i class="fas fa-lock"></i> كلمة المرور
                    </label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                
                <button type="submit" class="btn btn-primary btn-modern w-100 mb-3">
                    <i class="fas fa-sign-in-alt"></i> تسجيل الدخول
                </button>
            </form>
            
            <div class="alert alert-info mt-3">
                <h6 class="alert-heading">بيانات الدخول التجريبية:</h6>
                <small>
                    <strong>المدير:</strong> admin / admin123<br>
                    <strong>المعتمد:</strong> approver / approver123<br>
                    <strong>أمين الصندوق:</strong> cashier / cashier123<br>
                    <strong>المراجع:</strong> auditor / auditor123
                </small>
            </div>
        </div>
    </div>
    '''
    
    return render_template_string(MAIN_TEMPLATE, content=content, title='تسجيل الدخول')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_audit('تسجيل خروج', 'users', session['user_id'])
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    c = conn.cursor()
    
    # إحصائيات عامة
    today = date.today()
    
    # عدد الخزائن
    c.execute("SELECT COUNT(*) as count FROM cashboxes WHERE is_active = 1")
    cashbox_count = c.fetchone()['count']
    
    # معاملات اليوم
    c.execute("""SELECT 
                    COUNT(*) as count,
                    SUM(CASE WHEN txn_type IN ('receipt', 'transfer_in') THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN txn_type IN ('payment', 'transfer_out') THEN amount ELSE 0 END) as expense
                 FROM transactions 
                 WHERE date = ? AND status = 'approved'""", (today,))
    today_stats = c.fetchone()
    
    # المعاملات المعلقة
    c.execute("SELECT COUNT(*) as count FROM transactions WHERE status = 'draft'")
    pending_count = c.fetchone()['count']
    
    # أرصدة الخزائن
    c.execute("SELECT * FROM cashboxes WHERE is_active = 1")
    cashboxes = []
    total_balance = 0
    for box in c.fetchall():
        balance = calculate_balance(box['id'])
        total_balance += balance
        cashboxes.append({
            'id': box['id'],
            'code': box['code'],
            'name': box['name'],
            'currency': box['currency'],
            'balance': balance
        })
    
    # آخر المعاملات
    c.execute("""SELECT t.*, c.name as cashbox_name, cat.name as category_name, p.name as partner_name
                 FROM transactions t
                 LEFT JOIN cashboxes c ON t.cashbox_id = c.id
                 LEFT JOIN categories cat ON t.category_id = cat.id
                 LEFT JOIN partners p ON t.partner_id = p.id
                 ORDER BY t.created_at DESC
                 LIMIT 5""")
    recent_transactions = c.fetchall()
    
    conn.close()
    
    # بناء الصفحة
    navbar = f'''
    <nav class="navbar main-navbar fixed-top">
        <div class="container-fluid">
            <div class="navbar-brand">
                <i class="fas fa-cash-register"></i>
                نظام إدارة الخزينة الاحترافي
            </div>
            
            <div class="user-menu">
                <span>مرحباً، {session['full_name']}</span>
                <div class="user-avatar">{session['username'][0].upper()}</div>
                <a href="/logout" class="btn btn-light btn-sm">
                    <i class="fas fa-sign-out-alt"></i> خروج
                </a>
            </div>
        </div>
    </nav>
    '''
    
    sidebar = f'''
    <aside class="sidebar">
        <div class="sidebar-menu">
            <div class="sidebar-item">
                <a href="/dashboard" class="sidebar-link active">
                    <i class="fas fa-tachometer-alt"></i>
                    <span>لوحة التحكم</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/transactions" class="sidebar-link">
                    <i class="fas fa-exchange-alt"></i>
                    <span>المعاملات</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/cashboxes" class="sidebar-link">
                    <i class="fas fa-cash-register"></i>
                    <span>الخزائن</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/partners" class="sidebar-link">
                    <i class="fas fa-users"></i>
                    <span>الشركاء</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/categories" class="sidebar-link">
                    <i class="fas fa-tags"></i>
                    <span>التصنيفات</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/reports" class="sidebar-link">
                    <i class="fas fa-chart-bar"></i>
                    <span>التقارير</span>
                </a>
            </div>
            
            {'<div class="sidebar-item"><a href="/settings" class="sidebar-link"><i class="fas fa-cog"></i><span>الإعدادات</span></a></div>' if session['role'] == 'admin' else ''}
        </div>
    </aside>
    '''
    
    content = navbar + sidebar + f'''
    <div class="main-content">
        <div class="container-fluid">
            <!-- العنوان -->
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h2 class="animate-in">
                    <i class="fas fa-tachometer-alt"></i> لوحة التحكم
                </h2>
                <div>
                    <a href="/transactions/new" class="btn btn-primary btn-modern">
                        <i class="fas fa-plus"></i> معاملة جديدة
                    </a>
                    <a href="/transfers/new" class="btn btn-success btn-modern">
                        <i class="fas fa-exchange-alt"></i> تحويل بين الخزائن
                    </a>
                </div>
            </div>
            
            <!-- الإحصائيات -->
            <div class="row mb-4">
                <div class="col-md-3 mb-3">
                    <div class="stat-card primary animate-in">
                        <i class="fas fa-coins stat-icon"></i>
                        <div class="stat-value">{total_balance:,.2f}</div>
                        <div class="stat-label">إجمالي الأرصدة</div>
                    </div>
                </div>
                
                <div class="col-md-3 mb-3">
                    <div class="stat-card success animate-in" style="animation-delay: 0.1s;">
                        <i class="fas fa-arrow-down stat-icon"></i>
                        <div class="stat-value">{today_stats['income'] or 0:,.2f}</div>
                        <div class="stat-label">مقبوضات اليوم</div>
                    </div>
                </div>
                
                <div class="col-md-3 mb-3">
                    <div class="stat-card danger animate-in" style="animation-delay: 0.2s;">
                        <i class="fas fa-arrow-up stat-icon"></i>
                        <div class="stat-value">{today_stats['expense'] or 0:,.2f}</div>
                        <div class="stat-label">مدفوعات اليوم</div>
                    </div>
                </div>
                
                <div class="col-md-3 mb-3">
                    <div class="stat-card warning animate-in" style="animation-delay: 0.3s;">
                        <i class="fas fa-clock stat-icon"></i>
                        <div class="stat-value">{pending_count}</div>
                        <div class="stat-label">معاملات معلقة</div>
                    </div>
                </div>
            </div>
            
            <!-- أرصدة الخزائن -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="data-table animate-in" style="animation-delay: 0.4s;">
                        <div class="table-header">
                            <h3><i class="fas fa-cash-register"></i> أرصدة الخزائن</h3>
                        </div>
                        <div class="table-responsive">
                            <table class="table">
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
    '''
    
    for box in cashboxes:
        content += f'''
                                    <tr>
                                        <td><strong>{box['code']}</strong></td>
                                        <td>{box['name']}</td>
                                        <td>{box['currency']}</td>
                                        <td><strong class="text-primary">{box['balance']:,.2f}</strong></td>
                                        <td><span class="badge bg-success">نشط</span></td>
                                    </tr>
        '''
    
    content += '''
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- آخر المعاملات -->
            <div class="row">
                <div class="col-12">
                    <div class="data-table animate-in" style="animation-delay: 0.5s;">
                        <div class="table-header">
                            <h3><i class="fas fa-history"></i> آخر المعاملات</h3>
                            <a href="/transactions" class="btn btn-light btn-sm">عرض الكل</a>
                        </div>
                        <div class="table-responsive">
                            <table class="table">
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
    
    for txn in recent_transactions:
        type_badge = {
            'receipt': '<span class="badge bg-success">قبض</span>',
            'payment': '<span class="badge bg-danger">صرف</span>',
            'transfer_in': '<span class="badge bg-info">تحويل وارد</span>',
            'transfer_out': '<span class="badge bg-warning">تحويل صادر</span>'
        }.get(txn['txn_type'], '')
        
        status_badge = {
            'approved': '<span class="badge bg-success">معتمد</span>',
            'draft': '<span class="badge bg-warning">مسودة</span>',
            'void': '<span class="badge bg-secondary">ملغي</span>'
        }.get(txn['status'], '')
        
        content += f'''
                                    <tr>
                                        <td><strong>{txn['voucher_no'] or '-'}</strong></td>
                                        <td>{txn['date']}</td>
                                        <td>{type_badge}</td>
                                        <td>{txn['cashbox_name']}</td>
                                        <td><strong>{txn['amount']:,.2f}</strong></td>
                                        <td>{status_badge}</td>
                                    </tr>
        '''
    
    content += '''
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return render_template_string(MAIN_TEMPLATE, content=content, title='لوحة التحكم')

@app.route('/transactions')
@login_required
def transactions():
    conn = get_db()
    c = conn.cursor()
    
    # الفلاتر
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    type_filter = request.args.get('type', '')
    
    # بناء الاستعلام
    query = """SELECT t.*, c.name as cashbox_name, cat.name as category_name, 
                      p.name as partner_name, u.full_name as created_by_name
               FROM transactions t
               LEFT JOIN cashboxes c ON t.cashbox_id = c.id
               LEFT JOIN categories cat ON t.category_id = cat.id
               LEFT JOIN partners p ON t.partner_id = p.id
               LEFT JOIN users u ON t.created_by = u.id
               WHERE 1=1"""
    
    params = []
    
    if search:
        query += " AND (t.voucher_no LIKE ? OR t.description LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    if status_filter:
        query += " AND t.status = ?"
        params.append(status_filter)
    
    if type_filter:
        query += " AND t.txn_type = ?"
        params.append(type_filter)
    
    query += " ORDER BY t.created_at DESC LIMIT 100"
    
    c.execute(query, params)
    transactions = c.fetchall()
    
    conn.close()
    
    # بناء الصفحة
    navbar = f'''
    <nav class="navbar main-navbar fixed-top">
        <div class="container-fluid">
            <div class="navbar-brand">
                <i class="fas fa-cash-register"></i>
                نظام إدارة الخزينة الاحترافي
            </div>
            
            <div class="user-menu">
                <span>مرحباً، {session['full_name']}</span>
                <div class="user-avatar">{session['username'][0].upper()}</div>
                <a href="/logout" class="btn btn-light btn-sm">
                    <i class="fas fa-sign-out-alt"></i> خروج
                </a>
            </div>
        </div>
    </nav>
    '''
    
    sidebar = '''
    <aside class="sidebar">
        <div class="sidebar-menu">
            <div class="sidebar-item">
                <a href="/dashboard" class="sidebar-link">
                    <i class="fas fa-tachometer-alt"></i>
                    <span>لوحة التحكم</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/transactions" class="sidebar-link active">
                    <i class="fas fa-exchange-alt"></i>
                    <span>المعاملات</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/cashboxes" class="sidebar-link">
                    <i class="fas fa-cash-register"></i>
                    <span>الخزائن</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/partners" class="sidebar-link">
                    <i class="fas fa-users"></i>
                    <span>الشركاء</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/categories" class="sidebar-link">
                    <i class="fas fa-tags"></i>
                    <span>التصنيفات</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/reports" class="sidebar-link">
                    <i class="fas fa-chart-bar"></i>
                    <span>التقارير</span>
                </a>
            </div>
        </div>
    </aside>
    '''
    
    content = navbar + sidebar + f'''
    <div class="main-content">
        <div class="container-fluid">
            <!-- العنوان -->
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h2><i class="fas fa-exchange-alt"></i> المعاملات</h2>
                <div>
                    <a href="/transactions/new" class="btn btn-primary btn-modern">
                        <i class="fas fa-plus"></i> معاملة جديدة
                    </a>
                    <a href="/transfers/new" class="btn btn-success btn-modern">
                        <i class="fas fa-exchange-alt"></i> تحويل
                    </a>
                </div>
            </div>
            
            <!-- الفلاتر -->
            <div class="card mb-4">
                <div class="card-body">
                    <form method="GET" class="row g-3">
                        <div class="col-md-4">
                            <input type="text" name="search" class="form-control" 
                                   placeholder="بحث..." value="{search}">
                        </div>
                        <div class="col-md-2">
                            <select name="type" class="form-select">
                                <option value="">كل الأنواع</option>
                                <option value="receipt" {'selected' if type_filter == 'receipt' else ''}>قبض</option>
                                <option value="payment" {'selected' if type_filter == 'payment' else ''}>صرف</option>
                                <option value="transfer_in" {'selected' if type_filter == 'transfer_in' else ''}>تحويل وارد</option>
                                <option value="transfer_out" {'selected' if type_filter == 'transfer_out' else ''}>تحويل صادر</option>
                            </select>
                        </div>
                        <div class="col-md-2">
                            <select name="status" class="form-select">
                                <option value="">كل الحالات</option>
                                <option value="draft" {'selected' if status_filter == 'draft' else ''}>مسودة</option>
                                <option value="approved" {'selected' if status_filter == 'approved' else ''}>معتمد</option>
                                <option value="void" {'selected' if status_filter == 'void' else ''}>ملغي</option>
                            </select>
                        </div>
                        <div class="col-md-2">
                            <button type="submit" class="btn btn-primary w-100">
                                <i class="fas fa-search"></i> بحث
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- الجدول -->
            <div class="data-table">
                <div class="table-header">
                    <h3><i class="fas fa-list"></i> قائمة المعاملات</h3>
                </div>
                <div class="table-responsive">
                    <table class="table">
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
                                <th>أنشأها</th>
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
        }.get(txn['txn_type'], '')
        
        status_badge = {
            'approved': '<span class="badge bg-success">معتمد</span>',
            'draft': '<span class="badge bg-warning">مسودة</span>',
            'void': '<span class="badge bg-secondary">ملغي</span>'
        }.get(txn['status'], '')
        
        content += f'''
                            <tr>
                                <td><strong>{txn['voucher_no'] or '-'}</strong></td>
                                <td>{txn['date']}</td>
                                <td>{type_badge}</td>
                                <td>{txn['cashbox_name']}</td>
                                <td><strong>{txn['amount']:,.2f}</strong></td>
                                <td>{txn['category_name'] or '-'}</td>
                                <td>{txn['partner_name'] or '-'}</td>
                                <td>{status_badge}</td>
                                <td>{txn['created_by_name']}</td>
                                <td>
                                    <div class="btn-group btn-group-sm">
                                        <a href="/transactions/{txn['id']}" class="btn btn-outline-info">
                                            <i class="fas fa-eye"></i>
                                        </a>
        '''
        
        if txn['status'] == 'draft' and session['role'] in ['admin', 'approver']:
            content += f'''
                                        <button onclick="approveTransaction('{txn['id']}')" class="btn btn-outline-success">
                                            <i class="fas fa-check"></i>
                                        </button>
            '''
        
        content += '''
                                    </div>
                                </td>
                            </tr>
        '''
    
    content += '''
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function approveTransaction(id) {
        confirmAction('هل تريد اعتماد هذه المعاملة؟', function() {
            window.location.href = '/transactions/' + id + '/approve';
        });
    }
    </script>
    '''
    
    return render_template_string(MAIN_TEMPLATE, content=content, title='المعاملات')

@app.route('/transactions/new', methods=['GET', 'POST'])
@login_required
@check_permission('create')
def transaction_new():
    if request.method == 'POST':
        conn = get_db()
        c = conn.cursor()
        
        try:
            txn_id = str(uuid.uuid4())
            cashbox_id = request.form.get('cashbox_id')
            txn_type = request.form.get('txn_type')
            voucher_no = generate_voucher_no(cashbox_id, txn_type)
            
            c.execute("""INSERT INTO transactions 
                        (id, voucher_no, cashbox_id, txn_type, date, category_id, 
                         partner_id, description, amount, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (txn_id, voucher_no, cashbox_id, txn_type,
                       request.form.get('date'),
                       request.form.get('category_id') or None,
                       request.form.get('partner_id') or None,
                       request.form.get('description'),
                       float(request.form.get('amount')),
                       session['user_id']))
            
            conn.commit()
            log_audit('إنشاء معاملة', 'transactions', txn_id)
            conn.close()
            
            return '''<script>
                alert('تم إنشاء المعاملة بنجاح');
                window.location.href = '/transactions';
            </script>'''
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return f'''<script>
                alert('خطأ: {str(e)}');
                window.history.back();
            </script>'''
    
    # الحصول على البيانات للنموذج
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM cashboxes WHERE is_active = 1")
    cashboxes = c.fetchall()
    
    c.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY kind, name")
    categories = c.fetchall()
    
    c.execute("SELECT * FROM partners WHERE is_active = 1 ORDER BY name")
    partners = c.fetchall()
    
    conn.close()
    
    # بناء الصفحة
    navbar = f'''
    <nav class="navbar main-navbar fixed-top">
        <div class="container-fluid">
            <div class="navbar-brand">
                <i class="fas fa-cash-register"></i>
                نظام إدارة الخزينة الاحترافي
            </div>
            
            <div class="user-menu">
                <span>مرحباً، {session['full_name']}</span>
                <div class="user-avatar">{session['username'][0].upper()}</div>
                <a href="/logout" class="btn btn-light btn-sm">
                    <i class="fas fa-sign-out-alt"></i> خروج
                </a>
            </div>
        </div>
    </nav>
    '''
    
    sidebar = '''
    <aside class="sidebar">
        <div class="sidebar-menu">
            <div class="sidebar-item">
                <a href="/dashboard" class="sidebar-link">
                    <i class="fas fa-tachometer-alt"></i>
                    <span>لوحة التحكم</span>
                </a>
            </div>
            
            <div class="sidebar-item">
                <a href="/transactions" class="sidebar-link active">
                    <i class="fas fa-exchange-alt"></i>
                    <span>المعاملات</span>
                </a>
            </div>
        </div>
    </aside>
    '''
    
    content = navbar + sidebar + f'''
    <div class="main-content">
        <div class="container-fluid">
            <div class="row">
                <div class="col-md-8 mx-auto">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h4 class="mb-0">
                                <i class="fas fa-plus"></i> معاملة جديدة
                            </h4>
                        </div>
                        <div class="card-body">
                            <form method="POST" class="form-modern">
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
    '''
    
    for box in cashboxes:
        content += f'<option value="{box["id"]}">{box["name"]} ({box["code"]})</option>'
    
    content += f'''
                                        </select>
                                    </div>
                                </div>
                                
                                <div class="row mb-3">
                                    <div class="col-md-6">
                                        <label class="form-label">التاريخ *</label>
                                        <input type="date" name="date" class="form-control" 
                                               value="{date.today()}" required>
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
    '''
    
    for cat in categories:
        content += f'<option value="{cat["id"]}">{cat["name"]} ({cat["kind"]})</option>'
    
    content += '''
                                        </select>
                                    </div>
                                    
                                    <div class="col-md-6">
                                        <label class="form-label">الشريك</label>
                                        <select name="partner_id" class="form-select">
                                            <option value="">اختر...</option>
    '''
    
    for partner in partners:
        content += f'<option value="{partner["id"]}">{partner["name"]} ({partner["kind"]})</option>'
    
    content += '''
                                        </select>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">الوصف</label>
                                    <textarea name="description" class="form-control" rows="3"></textarea>
                                </div>
                                
                                <div class="d-flex justify-content-between">
                                    <button type="submit" class="btn btn-primary btn-modern">
                                        <i class="fas fa-save"></i> حفظ المعاملة
                                    </button>
                                    <a href="/transactions" class="btn btn-secondary btn-modern">
                                        <i class="fas fa-times"></i> إلغاء
                                    </a>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    '''
    
    return render_template_string(MAIN_TEMPLATE, content=content, title='معاملة جديدة')

@app.route('/transactions/<txn_id>/approve')
@login_required
@check_permission('approve')
def transaction_approve(txn_id):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("UPDATE transactions SET status = 'approved', approved_by = ? WHERE id = ? AND status = 'draft'",
              (session['user_id'], txn_id))
    
    if c.rowcount > 0:
        conn.commit()
        log_audit('اعتماد معاملة', 'transactions', txn_id)
    
    conn.close()
    return redirect('/transactions')

@app.route('/health')
def health():
    return 'OK', 200

# تشغيل التطبيق
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
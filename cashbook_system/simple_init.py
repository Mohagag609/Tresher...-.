#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

# Create instance directory
os.makedirs('instance', exist_ok=True)

# Connect to database
conn = sqlite3.connect('instance/cashbook.db')
cursor = conn.cursor()

# Create tables
cursor.executescript('''
-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) UNIQUE NOT NULL,
    name_ar VARCHAR(50),
    description VARCHAR(200),
    can_create_draft BOOLEAN DEFAULT 0,
    can_approve BOOLEAN DEFAULT 0,
    can_void BOOLEAN DEFAULT 0,
    can_manage_cashbox BOOLEAN DEFAULT 0,
    can_manage_users BOOLEAN DEFAULT 0,
    can_view_reports BOOLEAN DEFAULT 0,
    can_export BOOLEAN DEFAULT 0,
    can_close_period BOOLEAN DEFAULT 0
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    full_name_ar VARCHAR(100),
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT 1,
    is_superuser BOOLEAN DEFAULT 0,
    role_id INTEGER REFERENCES roles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- CashBoxes table
CREATE TABLE IF NOT EXISTS cashboxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_ar VARCHAR(100),
    description TEXT,
    currency VARCHAR(3) DEFAULT 'EGP',
    opening_balance DECIMAL(15,2) DEFAULT 0.00,
    box_type VARCHAR(20) DEFAULT 'main',
    is_active BOOLEAN DEFAULT 1,
    branch_name VARCHAR(100),
    branch_code VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) UNIQUE,
    name VARCHAR(120) NOT NULL,
    name_ar VARCHAR(120),
    category_type VARCHAR(20) NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    icon VARCHAR(50),
    color VARCHAR(7),
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    monthly_budget DECIMAL(15,2),
    yearly_budget DECIMAL(15,2),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Partners table
CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) UNIQUE,
    name VARCHAR(150) NOT NULL,
    name_ar VARCHAR(150),
    partner_type VARCHAR(20) DEFAULT 'other',
    phone VARCHAR(30),
    mobile VARCHAR(30),
    email VARCHAR(120),
    address TEXT,
    tax_number VARCHAR(50),
    commercial_register VARCHAR(50),
    bank_name VARCHAR(100),
    bank_account VARCHAR(50),
    bank_branch VARCHAR(100),
    is_active BOOLEAN DEFAULT 1,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cash Transactions table
CREATE TABLE IF NOT EXISTS cash_transactions (
    id VARCHAR(36) PRIMARY KEY,
    voucher_no VARCHAR(30) UNIQUE NOT NULL,
    cashbox_id INTEGER NOT NULL REFERENCES cashboxes(id),
    txn_type VARCHAR(20) NOT NULL,
    status VARCHAR(10) DEFAULT 'draft',
    date DATE NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EGP',
    exchange_rate DECIMAL(12,6) DEFAULT 1.000000,
    amount_base DECIMAL(15,2),
    category_id INTEGER REFERENCES categories(id),
    partner_id INTEGER REFERENCES partners(id),
    project_code VARCHAR(50),
    cost_center VARCHAR(50),
    description TEXT,
    reference_no VARCHAR(100),
    linked_txn_id VARCHAR(36) REFERENCES cash_transactions(id),
    created_by_id INTEGER NOT NULL REFERENCES users(id),
    approved_by_id INTEGER REFERENCES users(id),
    voided_by_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    voided_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    void_reason TEXT
);

-- Audit Log table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(80),
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    action VARCHAR(50) NOT NULL,
    model_name VARCHAR(50),
    record_id VARCHAR(50),
    old_values TEXT,
    new_values TEXT,
    description TEXT,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')

# Insert default data
print("✓ تم إنشاء جداول قاعدة البيانات")

# Insert roles
roles = [
    ('admin', 'مدير النظام', 'صلاحيات كاملة', 1, 1, 1, 1, 1, 1, 1, 1),
    ('approver', 'معتمد', 'اعتماد السندات', 1, 1, 1, 0, 0, 1, 1, 0),
    ('cashier', 'أمين صندوق', 'إنشاء السندات', 1, 0, 0, 0, 0, 1, 0, 0),
    ('auditor', 'مراجع', 'عرض التقارير', 0, 0, 0, 0, 0, 1, 1, 0)
]

for role in roles:
    cursor.execute('''INSERT OR IGNORE INTO roles 
        (name, name_ar, description, can_create_draft, can_approve, can_void, 
         can_manage_cashbox, can_manage_users, can_view_reports, can_export, can_close_period)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', role)

print("✓ تم إنشاء الأدوار الافتراضية")

# Insert admin user
admin_password = generate_password_hash('admin123')
cursor.execute('''INSERT OR IGNORE INTO users 
    (username, email, password_hash, full_name, full_name_ar, is_active, is_superuser, role_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
    ('admin', 'admin@cashbook.com', admin_password, 'System Admin', 'مدير النظام', 1, 1, 1))

# Insert demo user
demo_password = generate_password_hash('demo123')
cursor.execute('''INSERT OR IGNORE INTO users 
    (username, email, password_hash, full_name, full_name_ar, is_active, is_superuser, role_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
    ('demo', 'demo@cashbook.com', demo_password, 'Demo User', 'مستخدم تجريبي', 1, 0, 3))

print("✓ تم إنشاء المستخدمين (admin/admin123) و (demo/demo123)")

# Insert cashboxes
cashboxes = [
    ('MAIN', 'Main Cash Box', 'الخزنة الرئيسية', 'الخزنة الرئيسية للشركة', 'EGP', 10000.00, 'main', 1),
    ('PETTY', 'Petty Cash', 'العهدة النثرية', 'عهدة المصروفات النثرية', 'EGP', 2000.00, 'petty', 1),
    ('BANK', 'Bank Account', 'الحساب البنكي', 'الحساب البنكي الرئيسي', 'EGP', 50000.00, 'main', 1)
]

for box in cashboxes:
    cursor.execute('''INSERT OR IGNORE INTO cashboxes 
        (code, name, name_ar, description, currency, opening_balance, box_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', box)

print("✓ تم إنشاء الخزائن الافتراضية")

# Insert categories
categories = [
    ('SALES', 'Sales', 'المبيعات', 'income', '#10b981'),
    ('SERVICE', 'Services', 'الخدمات', 'income', '#06b6d4'),
    ('OTHER_INC', 'Other Income', 'إيرادات أخرى', 'income', '#8b5cf6'),
    ('SALARY', 'Salaries', 'الرواتب', 'expense', '#ef4444'),
    ('RENT', 'Rent', 'الإيجار', 'expense', '#f59e0b'),
    ('UTILITIES', 'Utilities', 'المرافق', 'expense', '#ec4899'),
    ('SUPPLIES', 'Office Supplies', 'مستلزمات مكتبية', 'expense', '#a855f7'),
    ('TRANSPORT', 'Transportation', 'المواصلات', 'expense', '#3b82f6'),
    ('MARKETING', 'Marketing', 'التسويق', 'expense', '#14b8a6'),
    ('OTHER_EXP', 'Other Expenses', 'مصروفات أخرى', 'expense', '#6b7280'),
    ('TRANSFER', 'Transfer', 'تحويل', 'transfer', '#0ea5e9')
]

for cat in categories:
    cursor.execute('''INSERT OR IGNORE INTO categories 
        (code, name, name_ar, category_type, color, is_active)
        VALUES (?, ?, ?, ?, ?, 1)''', cat)

print("✓ تم إنشاء التصنيفات الافتراضية")

# Insert partners
partners = [
    ('CUST001', 'Ahmed Mohamed', 'أحمد محمد', 'customer', '01012345678', 'ahmed@example.com'),
    ('SUPP001', 'ABC Company', 'شركة أي بي سي', 'supplier', '0223456789', 'info@abc.com'),
    ('EMP001', 'Mohamed Ali', 'محمد علي', 'employee', '01098765432', 'mohamed@company.com')
]

for partner in partners:
    cursor.execute('''INSERT OR IGNORE INTO partners 
        (code, name, name_ar, partner_type, phone, email, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)''', partner)

print("✓ تم إنشاء الشركاء الافتراضيين")

# Commit and close
conn.commit()
conn.close()

print("\n" + "="*50)
print("تم إعداد قاعدة البيانات بنجاح!")
print("="*50)
print("\nيمكنك الآن تشغيل البرنامج:")
print("  python3 run.py")
print("\nبيانات الدخول:")
print("  المدير: admin / admin123")
print("  تجريبي: demo / demo123")
print("="*50)
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import os
from werkzeug.security import generate_password_hash

print("🔧 إصلاح قاعدة البيانات...")

# Create instance directory
os.makedirs('instance', exist_ok=True)

# Connect to database
conn = sqlite3.connect('instance/cashbook.db')
cursor = conn.cursor()

# Drop all tables and recreate
cursor.execute('DROP TABLE IF EXISTS users')
cursor.execute('DROP TABLE IF EXISTS cashboxes')
cursor.execute('DROP TABLE IF EXISTS cash_transactions')

# Create users table
cursor.execute('''
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120),
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    full_name_ar VARCHAR(100),
    is_active INTEGER DEFAULT 1,
    is_superuser INTEGER DEFAULT 0
)
''')

# Create cashboxes table with balance column
cursor.execute('''
CREATE TABLE cashboxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_ar VARCHAR(100),
    currency VARCHAR(3) DEFAULT 'EGP',
    balance DECIMAL(15,2) DEFAULT 0.00,
    opening_balance DECIMAL(15,2) DEFAULT 0.00,
    is_active INTEGER DEFAULT 1
)
''')

# Create transactions table
cursor.execute('''
CREATE TABLE cash_transactions (
    id VARCHAR(36) PRIMARY KEY,
    voucher_no VARCHAR(30),
    amount DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Insert users
admin_password = generate_password_hash('admin123')
cursor.execute('''
INSERT INTO users (username, email, password_hash, full_name, full_name_ar, is_active, is_superuser)
VALUES (?, ?, ?, ?, ?, ?, ?)
''', ('admin', 'admin@cashbook.com', admin_password, 'System Admin', 'مدير النظام', 1, 1))

demo_password = generate_password_hash('demo123')
cursor.execute('''
INSERT INTO users (username, email, password_hash, full_name, full_name_ar, is_active, is_superuser)
VALUES (?, ?, ?, ?, ?, ?, ?)
''', ('demo', 'demo@cashbook.com', demo_password, 'Demo User', 'مستخدم تجريبي', 1, 0))

# Insert cashboxes with balance
cursor.execute('''
INSERT INTO cashboxes (code, name, name_ar, currency, balance, opening_balance, is_active)
VALUES 
    ('MAIN', 'Main Cash Box', 'الخزنة الرئيسية', 'EGP', 10000.00, 10000.00, 1),
    ('PETTY', 'Petty Cash', 'العهدة النثرية', 'EGP', 2000.00, 2000.00, 1),
    ('BANK', 'Bank Account', 'الحساب البنكي', 'EGP', 50000.00, 50000.00, 1)
''')

conn.commit()
conn.close()

print("✅ تم إصلاح قاعدة البيانات بنجاح!")
print("\n📝 بيانات الدخول:")
print("   المدير: admin / admin123")
print("   تجريبي: demo / demo123")
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cashbook-secret-key-2024')

# Simple HTML templates
LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; align-items: center; justify-content: center; }
        .login-box { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); width: 400px; }
        h2 { text-align: center; margin-bottom: 30px; color: #333; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; color: #666; }
        input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
        button { width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; }
        button:hover { background: #5a67d8; }
        .error { background: #fee; color: #c33; padding: 10px; border-radius: 5px; margin-bottom: 20px; text-align: center; }
        .info { background: #e0f2fe; color: #0369a1; padding: 15px; border-radius: 5px; margin-top: 20px; }
        .info h3 { margin-bottom: 10px; }
        .info p { margin: 5px 0; font-family: monospace; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🏦 نظام إدارة الخزينة</h2>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label>اسم المستخدم</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>كلمة المرور</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">دخول</button>
        </form>
        <div class="info">
            <h3>بيانات الدخول:</h3>
            <p>👤 المدير: admin / admin123</p>
            <p>👤 تجريبي: demo / demo123</p>
        </div>
    </div>
</body>
</html>
'''

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: #f5f5f5; }
        .header { background: white; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; }
        .header h1 { color: #333; font-size: 24px; }
        .logout { background: #dc3545; color: white; padding: 8px 20px; text-decoration: none; border-radius: 5px; }
        .logout:hover { background: #c82333; }
        .container { padding: 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; }
        .stat-card .value { font-size: 32px; font-weight: bold; color: #333; }
        .stat-card.blue { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
        .stat-card.blue h3 { color: rgba(255,255,255,0.9); }
        .stat-card.blue .value { color: white; }
        .stat-card.green { background: linear-gradient(135deg, #00d2ff, #3a7bd5); color: white; }
        .stat-card.green h3 { color: rgba(255,255,255,0.9); }
        .stat-card.green .value { color: white; }
        .table-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; }
        th { background: #f8f9fa; padding: 12px; text-align: right; border-bottom: 2px solid #dee2e6; }
        td { padding: 12px; border-bottom: 1px solid #dee2e6; }
        .badge { background: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
        .actions { margin-top: 30px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .action-btn { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; text-decoration: none; color: #333; transition: transform 0.2s; }
        .action-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
        .action-btn .icon { font-size: 32px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏦 نظام إدارة الخزينة - لوحة التحكم</h1>
        <div>
            <span style="margin-left: 20px;">مرحباً {{ username }}</span>
            <a href="/logout" class="logout">خروج</a>
        </div>
    </div>
    
    <div class="container">
        <div class="stats">
            <div class="stat-card blue">
                <h3>إجمالي الرصيد</h3>
                <div class="value">{{ total_balance }} جنيه</div>
            </div>
            <div class="stat-card green">
                <h3>عدد الخزائن</h3>
                <div class="value">{{ cashbox_count }}</div>
            </div>
            <div class="stat-card">
                <h3>مقبوضات اليوم</h3>
                <div class="value">15,000 جنيه</div>
            </div>
            <div class="stat-card">
                <h3>مدفوعات اليوم</h3>
                <div class="value">8,500 جنيه</div>
            </div>
        </div>
        
        <div class="table-container">
            <h2 style="margin-bottom: 20px;">الخزائن النشطة</h2>
            <table>
                <thead>
                    <tr>
                        <th>الكود</th>
                        <th>الاسم</th>
                        <th>العملة</th>
                        <th>الرصيد</th>
                        <th>الحالة</th>
                    </tr>
                </thead>
                <tbody>
                    {% for box in cashboxes %}
                    <tr>
                        <td>{{ box[0] }}</td>
                        <td><strong>{{ box[1] }}</strong></td>
                        <td>{{ box[2] }}</td>
                        <td>{{ "{:,.2f}".format(box[3]) }}</td>
                        <td><span class="badge">نشط</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="actions">
            <a href="#" class="action-btn">
                <div class="icon">➕</div>
                <div>سند قبض جديد</div>
            </a>
            <a href="#" class="action-btn">
                <div class="icon">➖</div>
                <div>سند صرف جديد</div>
            </a>
            <a href="#" class="action-btn">
                <div class="icon">🔄</div>
                <div>تحويل بين الخزائن</div>
            </a>
            <a href="#" class="action-btn">
                <div class="icon">📊</div>
                <div>التقارير</div>
            </a>
        </div>
    </div>
</body>
</html>
'''

def init_db():
    """Initialize database with default data"""
    try:
        conn = sqlite3.connect('instance/cashbook.db')
        cursor = conn.cursor()
        
        # Drop and recreate tables to ensure correct schema
        cursor.execute('DROP TABLE IF EXISTS users')
        cursor.execute('DROP TABLE IF EXISTS cashboxes')
        
        # Create tables with correct schema
        cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            full_name TEXT
        )''')
        
        cursor.execute('''
        CREATE TABLE cashboxes (
            id INTEGER PRIMARY KEY,
            code TEXT,
            name TEXT,
            currency TEXT,
            balance REAL
        )''')
        
        # Add users
        admin_hash = generate_password_hash('admin123')
        demo_hash = generate_password_hash('demo123')
        
        cursor.execute('INSERT INTO users (username, password_hash, full_name) VALUES (?, ?, ?)',
                      ('admin', admin_hash, 'مدير النظام'))
        cursor.execute('INSERT INTO users (username, password_hash, full_name) VALUES (?, ?, ?)',
                      ('demo', demo_hash, 'مستخدم تجريبي'))
        
        # Add cashboxes with balance column
        cursor.execute('''INSERT INTO cashboxes (code, name, currency, balance) VALUES
                         ('MAIN', 'الخزنة الرئيسية', 'EGP', 10000),
                         ('PETTY', 'العهدة النثرية', 'EGP', 2000),
                         ('BANK', 'الحساب البنكي', 'EGP', 50000)''')
        
        conn.commit()
        conn.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database init error: {e}")
        if conn:
            conn.close()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        try:
            conn = sqlite3.connect('instance/cashbook.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, password_hash, full_name FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            conn.close()
            
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = user[2]
                return redirect('/dashboard')
            else:
                error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
        except Exception as e:
            error = f'خطأ في النظام: {str(e)}'
    
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    try:
        conn = sqlite3.connect('instance/cashbook.db')
        cursor = conn.cursor()
        cursor.execute('SELECT code, name, currency, balance FROM cashboxes')
        cashboxes = cursor.fetchall()
        conn.close()
        
        total = sum(box[3] for box in cashboxes)
        
        return render_template_string(DASHBOARD_HTML,
            username=session.get('username', 'المستخدم'),
            cashboxes=cashboxes,
            total_balance=f"{total:,.0f}",
            cashbox_count=len(cashboxes)
        )
    except Exception as e:
        return f'خطأ: {str(e)}', 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    os.makedirs('instance', exist_ok=True)
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
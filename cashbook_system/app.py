#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'cashbook-secret-key-2024'

# Initialize database once
def init_db():
    """Initialize database with users only"""
    try:
        os.makedirs('instance', exist_ok=True)
        conn = sqlite3.connect('instance/users.db')
        c = conn.cursor()
        
        # Create users table only
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY, 
                     username TEXT UNIQUE, 
                     password TEXT, 
                     fullname TEXT)''')
        
        # Check if admin exists
        c.execute("SELECT * FROM users WHERE username='admin'")
        if not c.fetchone():
            # Add default users
            admin_pass = generate_password_hash('admin123')
            demo_pass = generate_password_hash('demo123')
            
            c.execute("INSERT INTO users (username, password, fullname) VALUES (?, ?, ?)",
                     ('admin', admin_pass, 'مدير النظام'))
            c.execute("INSERT INTO users (username, password, fullname) VALUES (?, ?, ?)",
                     ('demo', demo_pass, 'مستخدم تجريبي'))
            
            conn.commit()
            print("Users database initialized successfully")
        
        conn.close()
    except Exception as e:
        print(f"Database init error: {e}")

# Initialize on startup
init_db()

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Arial', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .login-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
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
            font-size: 28px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: #666;
            font-size: 14px;
        }
        
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
        }
        
        .info-box {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
        }
        
        .info-box h4 {
            margin-bottom: 10px;
            color: #666;
        }
        
        .info-box p {
            margin: 5px 0;
            color: #888;
        }
        
        .error-msg {
            background: #fee;
            color: #c33;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .header {
            background: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            color: #333;
            font-size: 24px;
        }
        
        .header .user-info {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .logout-btn {
            background: #dc3545;
            color: white;
            padding: 8px 20px;
            text-decoration: none;
            border-radius: 6px;
            transition: background 0.3s;
        }
        
        .logout-btn:hover {
            background: #c82333;
        }
        
        .dashboard-container {
            padding: 30px;
            background: #f5f6fa;
            min-height: calc(100vh - 80px);
        }
        
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
        
        .stat-card h3 {
            font-size: 14px;
            margin-bottom: 10px;
            opacity: 0.8;
        }
        
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
        }
        
        .stat-card .unit {
            font-size: 14px;
            opacity: 0.7;
        }
        
        .table-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            overflow: hidden;
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
        
        tr:hover {
            background: #fafbfc;
        }
        
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
        
        .badge.info {
            background: #d1ecf1;
            color: #0c5460;
        }
    </style>
</head>
<body>
    {% if page == 'login' %}
    <div class="login-container">
        <div class="login-box">
            <h2>🏦 نظام إدارة الخزينة</h2>
            {% if error %}
            <div class="error-msg">{{ error }}</div>
            {% endif %}
            <form method="POST">
                <div class="form-group">
                    <label>اسم المستخدم</label>
                    <input type="text" name="username" required autofocus>
                </div>
                <div class="form-group">
                    <label>كلمة المرور</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn">تسجيل الدخول</button>
            </form>
            <div class="info-box">
                <h4>بيانات الدخول التجريبية:</h4>
                <p>👤 المدير: admin / admin123</p>
                <p>👤 مستخدم: demo / demo123</p>
            </div>
        </div>
    </div>
    {% elif page == 'dashboard' %}
    <div class="header">
        <h1>🏦 نظام إدارة الخزينة</h1>
        <div class="user-info">
            <span>مرحباً، {{ username }}</span>
            <a href="/logout" class="logout-btn">تسجيل الخروج</a>
        </div>
    </div>
    <div class="dashboard-container">
        <div class="stats-grid">
            <div class="stat-card primary">
                <h3>إجمالي الرصيد</h3>
                <div class="value">62,000 <span class="unit">جنيه</span></div>
            </div>
            <div class="stat-card">
                <h3>عدد الخزائن النشطة</h3>
                <div class="value">3 <span class="unit">خزنة</span></div>
            </div>
            <div class="stat-card">
                <h3>مقبوضات اليوم</h3>
                <div class="value">15,500 <span class="unit">جنيه</span></div>
            </div>
            <div class="stat-card">
                <h3>مدفوعات اليوم</h3>
                <div class="value">8,200 <span class="unit">جنيه</span></div>
            </div>
        </div>
        
        <div class="table-container">
            <div class="table-header">📊 أرصدة الخزائن</div>
            <table>
                <thead>
                    <tr>
                        <th>كود الخزنة</th>
                        <th>اسم الخزنة</th>
                        <th>العملة</th>
                        <th>الرصيد الحالي</th>
                        <th>الحالة</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>MAIN</strong></td>
                        <td>الخزنة الرئيسية</td>
                        <td>EGP</td>
                        <td><strong>10,000</strong> جنيه</td>
                        <td><span class="badge success">نشط</span></td>
                    </tr>
                    <tr>
                        <td><strong>PETTY</strong></td>
                        <td>العهدة النثرية</td>
                        <td>EGP</td>
                        <td><strong>2,000</strong> جنيه</td>
                        <td><span class="badge success">نشط</span></td>
                    </tr>
                    <tr>
                        <td><strong>BANK</strong></td>
                        <td>الحساب البنكي</td>
                        <td>EGP</td>
                        <td><strong>50,000</strong> جنيه</td>
                        <td><span class="badge success">نشط</span></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    {% endif %}
</body>
</html>
'''

@app.route('/')
def index():
    if 'user' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        try:
            conn = sqlite3.connect('instance/users.db')
            c = conn.cursor()
            c.execute("SELECT password, fullname FROM users WHERE username=?", (username,))
            user = c.fetchone()
            conn.close()
            
            if user and check_password_hash(user[0], password):
                session['user'] = username
                session['fullname'] = user[1]
                return redirect('/dashboard')
            else:
                error = 'خطأ في اسم المستخدم أو كلمة المرور'
        except Exception as e:
            error = 'خطأ في النظام'
            print(f"Login error: {e}")
    
    return render_template_string(HTML_TEMPLATE, page='login', title='تسجيل الدخول', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    
    username = session.get('fullname', session.get('user', 'المستخدم'))
    return render_template_string(HTML_TEMPLATE, page='dashboard', title='لوحة التحكم', username=username)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "message": "Application is running"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
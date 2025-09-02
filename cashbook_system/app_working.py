#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'cashbook-2024-secret'

# HTML Templates
LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            height: 100vh; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            font-family: Arial, sans-serif;
        }
        .login-box { 
            background: white; 
            padding: 40px; 
            border-radius: 10px; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.2); 
            width: 400px; 
        }
        h2 { text-align: center; margin-bottom: 30px; }
        input { 
            width: 100%; 
            padding: 10px; 
            margin: 10px 0; 
            border: 1px solid #ddd; 
            border-radius: 5px; 
        }
        button { 
            width: 100%; 
            padding: 12px; 
            background: #667eea; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
            font-size: 16px;
        }
        .info { 
            background: #f0f0f0; 
            padding: 15px; 
            margin-top: 20px; 
            border-radius: 5px; 
        }
        .error { 
            background: #ffcccc; 
            color: #cc0000; 
            padding: 10px; 
            margin: 10px 0; 
            border-radius: 5px; 
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>نظام إدارة الخزينة</h2>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول</button>
        </form>
        <div class="info">
            <strong>بيانات الدخول:</strong><br>
            المدير: admin / admin123<br>
            تجريبي: demo / demo123
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
    <title>لوحة التحكم</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: #f5f5f5; 
            font-family: Arial, sans-serif;
        }
        .header { 
            background: white; 
            padding: 20px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
            display: flex; 
            justify-content: space-between; 
        }
        .container { padding: 20px; }
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px; 
        }
        .card { 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }
        .card h3 { 
            color: #666; 
            font-size: 14px; 
            margin-bottom: 10px; 
        }
        .card .value { 
            font-size: 28px; 
            font-weight: bold; 
            color: #333; 
        }
        .card.blue { 
            background: linear-gradient(135deg, #667eea, #764ba2); 
            color: white; 
        }
        .card.blue h3 { color: rgba(255,255,255,0.9); }
        .card.blue .value { color: white; }
        table { 
            width: 100%; 
            background: white; 
            border-radius: 10px; 
            overflow: hidden; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }
        th { 
            background: #667eea; 
            color: white; 
            padding: 15px; 
            text-align: right; 
        }
        td { 
            padding: 15px; 
            border-bottom: 1px solid #eee; 
        }
        .logout { 
            background: #dc3545; 
            color: white; 
            padding: 8px 20px; 
            text-decoration: none; 
            border-radius: 5px; 
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>نظام إدارة الخزينة</h1>
        <div>
            <span>مرحباً {{ username }}</span>
            <a href="/logout" class="logout">خروج</a>
        </div>
    </div>
    
    <div class="container">
        <div class="stats">
            <div class="card blue">
                <h3>إجمالي الرصيد</h3>
                <div class="value">62,000 جنيه</div>
            </div>
            <div class="card">
                <h3>عدد الخزائن</h3>
                <div class="value">3</div>
            </div>
            <div class="card">
                <h3>مقبوضات اليوم</h3>
                <div class="value">15,000 جنيه</div>
            </div>
            <div class="card">
                <h3>مدفوعات اليوم</h3>
                <div class="value">8,500 جنيه</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>الكود</th>
                    <th>اسم الخزنة</th>
                    <th>العملة</th>
                    <th>الرصيد</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>MAIN</td>
                    <td>الخزنة الرئيسية</td>
                    <td>EGP</td>
                    <td>10,000</td>
                </tr>
                <tr>
                    <td>PETTY</td>
                    <td>العهدة النثرية</td>
                    <td>EGP</td>
                    <td>2,000</td>
                </tr>
                <tr>
                    <td>BANK</td>
                    <td>الحساب البنكي</td>
                    <td>EGP</td>
                    <td>50,000</td>
                </tr>
            </tbody>
        </table>
    </div>
</body>
</html>
'''

# Initialize database
def init_db():
    try:
        os.makedirs('instance', exist_ok=True)
        conn = sqlite3.connect('instance/cashbook.db')
        c = conn.cursor()
        
        # Create users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY, username TEXT UNIQUE, 
                     password TEXT, fullname TEXT)''')
        
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
            print("Database initialized with default users")
        
        conn.close()
    except Exception as e:
        print(f"Database error: {e}")

@app.route('/')
def home():
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
            conn = sqlite3.connect('instance/cashbook.db')
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
            error = f'خطأ في النظام'
    
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    
    username = session.get('fullname', session.get('user', 'المستخدم'))
    return render_template_string(DASHBOARD_HTML, username=username)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/health')
def health():
    return 'OK'

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
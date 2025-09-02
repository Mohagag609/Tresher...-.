#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-2024')

# Ensure database exists
os.makedirs('instance', exist_ok=True)

# HTML Templates as strings to avoid template issues
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - نظام الخزينة</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@200;300;400;500;600;700;800;900&display=swap');
        * { font-family: 'Cairo', sans-serif; }
    </style>
</head>
<body>
<div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500">
    <div class="max-w-md w-full">
        <div class="bg-white rounded-2xl shadow-2xl p-8">
            <div class="text-center">
                <div class="mx-auto h-20 w-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center">
                    <i class="fas fa-cash-register text-white text-3xl"></i>
                </div>
                <h2 class="mt-6 text-3xl font-extrabold text-gray-900">نظام إدارة الخزينة</h2>
                <p class="mt-2 text-sm text-gray-600">قم بتسجيل الدخول للوصول إلى حسابك</p>
            </div>
            
            {% if error %}
            <div class="mt-4 p-3 bg-red-100 text-red-700 rounded-lg">{{ error }}</div>
            {% endif %}
            
            <form class="mt-8 space-y-6" method="POST">
                <div>
                    <label class="block text-sm font-medium text-gray-700">اسم المستخدم</label>
                    <input type="text" name="username" required class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">كلمة المرور</label>
                    <input type="password" name="password" required class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
                </div>
                <button type="submit" class="w-full py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:from-indigo-700 hover:to-purple-700">
                    تسجيل الدخول
                </button>
            </form>
            
            <div class="mt-6 p-4 bg-blue-50 rounded-lg">
                <p class="text-sm text-blue-800 font-medium mb-2">بيانات الدخول:</p>
                <p class="text-xs text-blue-700">المدير: admin / admin123</p>
                <p class="text-xs text-blue-700">تجريبي: demo / demo123</p>
            </div>
        </div>
    </div>
</div>
</body>
</html>
'''

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم - نظام الخزينة</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@200;300;400;500;600;700;800;900&display=swap');
        * { font-family: 'Cairo', sans-serif; }
    </style>
</head>
<body class="bg-gray-50">
    <!-- Navigation -->
    <nav class="bg-white shadow-lg border-b">
        <div class="px-6 py-4">
            <div class="flex justify-between items-center">
                <div class="flex items-center">
                    <i class="fas fa-cash-register text-indigo-600 text-2xl ml-3"></i>
                    <span class="text-xl font-bold">نظام الخزينة</span>
                </div>
                <div class="flex items-center space-x-4 space-x-reverse">
                    <span class="text-gray-700">مرحباً {{ username }}</span>
                    <a href="/logout" class="text-red-600 hover:text-red-800">
                        <i class="fas fa-sign-out-alt ml-2"></i>خروج
                    </a>
                </div>
            </div>
        </div>
    </nav>
    
    <div class="container mx-auto px-6 py-8">
        <h1 class="text-3xl font-bold text-gray-800 mb-8">لوحة التحكم</h1>
        
        <!-- Statistics Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div class="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shadow-lg p-6 text-white">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-blue-100 text-sm">إجمالي الرصيد</p>
                        <p class="text-3xl font-bold mt-2">{{ total_balance }}</p>
                    </div>
                    <i class="fas fa-wallet text-3xl opacity-50"></i>
                </div>
            </div>
            
            <div class="bg-gradient-to-br from-green-500 to-green-600 rounded-lg shadow-lg p-6 text-white">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-green-100 text-sm">مقبوضات اليوم</p>
                        <p class="text-3xl font-bold mt-2">15,000</p>
                    </div>
                    <i class="fas fa-arrow-down text-3xl opacity-50"></i>
                </div>
            </div>
            
            <div class="bg-gradient-to-br from-red-500 to-red-600 rounded-lg shadow-lg p-6 text-white">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-red-100 text-sm">مدفوعات اليوم</p>
                        <p class="text-3xl font-bold mt-2">8,500</p>
                    </div>
                    <i class="fas fa-arrow-up text-3xl opacity-50"></i>
                </div>
            </div>
            
            <div class="bg-gradient-to-br from-yellow-500 to-yellow-600 rounded-lg shadow-lg p-6 text-white">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-yellow-100 text-sm">عدد المعاملات</p>
                        <p class="text-3xl font-bold mt-2">{{ transaction_count }}</p>
                    </div>
                    <i class="fas fa-file-invoice text-3xl opacity-50"></i>
                </div>
            </div>
        </div>
        
        <!-- Cashboxes Table -->
        <div class="bg-white rounded-lg shadow-lg p-6 mb-8">
            <h2 class="text-xl font-bold text-gray-800 mb-4">
                <i class="fas fa-box ml-2 text-indigo-600"></i>
                الخزائن
            </h2>
            <div class="overflow-x-auto">
                <table class="min-w-full">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">الكود</th>
                            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">الاسم</th>
                            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">العملة</th>
                            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">الرصيد</th>
                            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">الحالة</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
                        {% for box in cashboxes %}
                        <tr>
                            <td class="px-6 py-4 text-sm">{{ box[0] }}</td>
                            <td class="px-6 py-4 text-sm font-medium">{{ box[1] }}</td>
                            <td class="px-6 py-4 text-sm">{{ box[2] }}</td>
                            <td class="px-6 py-4 text-sm font-bold">{{ box[3] }}</td>
                            <td class="px-6 py-4">
                                <span class="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">نشط</span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Quick Actions -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <a href="#" class="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow">
                <div class="flex items-center">
                    <div class="bg-green-100 rounded-full p-3 ml-4">
                        <i class="fas fa-plus-circle text-green-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-gray-800">سند قبض جديد</h3>
                        <p class="text-sm text-gray-600">إضافة إيراد جديد</p>
                    </div>
                </div>
            </a>
            
            <a href="#" class="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow">
                <div class="flex items-center">
                    <div class="bg-red-100 rounded-full p-3 ml-4">
                        <i class="fas fa-minus-circle text-red-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-gray-800">سند صرف جديد</h3>
                        <p class="text-sm text-gray-600">إضافة مصروف جديد</p>
                    </div>
                </div>
            </a>
            
            <a href="#" class="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow">
                <div class="flex items-center">
                    <div class="bg-blue-100 rounded-full p-3 ml-4">
                        <i class="fas fa-exchange-alt text-blue-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-gray-800">تحويل بين الخزائن</h3>
                        <p class="text-sm text-gray-600">نقل الأموال</p>
                    </div>
                </div>
            </a>
        </div>
    </div>
</body>
</html>
'''

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    conn = sqlite3.connect('instance/cashbook.db')
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, password_hash, full_name FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            conn.close()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['full_name'] = user[3]
                return redirect(url_for('dashboard'))
            else:
                error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
        except Exception as e:
            error = f'خطأ في قاعدة البيانات: {str(e)}'
    
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get cashboxes
        cursor.execute('SELECT code, name, currency, opening_balance FROM cashboxes WHERE is_active = 1')
        cashboxes = cursor.fetchall()
        
        # Calculate total balance
        total_balance = sum(box[3] for box in cashboxes)
        
        # Get transaction count
        cursor.execute('SELECT COUNT(*) FROM cash_transactions')
        transaction_count = cursor.fetchone()[0]
        
        conn.close()
        
        return render_template_string(DASHBOARD_TEMPLATE,
            username=session.get('full_name', session.get('username')),
            cashboxes=cashboxes,
            total_balance=f"{total_balance:,.2f}",
            transaction_count=transaction_count
        )
    except Exception as e:
        return f"خطأ: {str(e)}", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    # Initialize database if not exists
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Initializing database...")
            import subprocess
            subprocess.run(['python', 'simple_init.py'])
        
        conn.close()
    except:
        pass
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import check_password_hash
import sqlite3
from datetime import datetime

# Create Flask app
app = Flask(__name__, template_folder='app/templates', static_folder='app/static')

# Configuration for Render
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-2024')
app.config['DATABASE_PATH'] = 'instance/cashbook.db'

# Ensure instance directory exists
os.makedirs('instance', exist_ok=True)
os.makedirs('app/static/uploads', exist_ok=True)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول للوصول لهذه الصفحة'

# Simple User class
class User(UserMixin):
    def __init__(self, id, username, email, full_name, is_superuser=False):
        self.id = id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.is_superuser = is_superuser
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def has_permission(self, permission):
        return self.is_superuser
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, full_name, is_superuser FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(*user_data)
    return None

# Routes
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, code, name, currency, opening_balance 
        FROM cashboxes WHERE is_active = 1
    ''')
    cashboxes_data = cursor.fetchall()
    
    cashboxes = []
    total_balance = 0
    for box in cashboxes_data:
        box_dict = {
            'box': {
                'id': box[0],
                'code': box[1],
                'name': box[2],
                'currency': box[3]
            },
            'balance': float(box[4]),
            'today_change': 0
        }
        cashboxes.append(box_dict)
        total_balance += box_dict['balance']
    
    cursor.execute('''
        SELECT id, voucher_no, txn_type, amount, status, date 
        FROM cash_transactions 
        ORDER BY created_at DESC LIMIT 10
    ''')
    transactions_data = cursor.fetchall()
    
    recent_transactions = []
    for txn in transactions_data:
        recent_transactions.append({
            'id': txn[0],
            'voucher_no': txn[1],
            'txn_type': txn[2],
            'amount': float(txn[3]) if txn[3] else 0,
            'status': txn[4],
            'date': datetime.strptime(txn[5], '%Y-%m-%d') if txn[5] else datetime.now()
        })
    
    conn.close()
    
    chart_labels = ['01/09', '02/09', '03/09', '04/09', '05/09', '06/09', '07/09']
    chart_receipts = [5000, 7500, 3000, 12000, 8000, 6500, 9000]
    chart_payments = [3000, 4500, 6000, 5500, 7000, 4000, 5000]
    
    return render_template('dashboard.html',
        cashboxes=cashboxes,
        total_balance=total_balance,
        today_receipts=15000,
        today_payments=8500,
        month_receipts=180000,
        month_payments=120000,
        recent_transactions=recent_transactions,
        pending_count=5,
        top_expense_categories=[],
        chart_labels=chart_labels,
        chart_receipts=chart_receipts,
        chart_payments=chart_payments
    )

@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, password_hash, full_name, is_superuser 
            FROM users WHERE username = ?
        ''', (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data and check_password_hash(user_data[3], password):
            user = User(user_data[0], user_data[1], user_data[2], user_data[4], user_data[5])
            login_user(user, remember=True)
            flash(f'مرحباً {user.full_name}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    class SimpleForm:
        def __init__(self):
            self.username = type('obj', (object,), {'label': type('obj', (object,), {'text': 'اسم المستخدم'})()})()
            self.password = type('obj', (object,), {'label': type('obj', (object,), {'text': 'كلمة المرور'})()})()
            self.remember_me = type('obj', (object,), {})()
            self.errors = []
        
        def hidden_tag(self):
            return ''
    
    return render_template('auth/login_simple.html')

@app.route('/auth/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('login'))

@app.route('/cashbox')
@login_required
def cashbox_index():
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, code, name, name_ar, currency, opening_balance, box_type, is_active 
        FROM cashboxes
    ''')
    cashboxes_data = cursor.fetchall()
    conn.close()
    
    cashboxes = []
    for box in cashboxes_data:
        cashboxes.append({
            'id': box[0],
            'code': box[1],
            'name': box[2],
            'name_ar': box[3],
            'currency': box[4],
            'opening_balance': float(box[5]),
            'current_balance': float(box[5]),
            'box_type': box[6],
            'is_active': box[7]
        })
    
    return render_template('cashbox/index.html', cashboxes=cashboxes)

@app.route('/transactions')
@login_required
def transactions_index():
    class SearchForm:
        def __init__(self):
            self.search = type('obj', (object,), {'data': ''})()
            self.cashbox_id = type('obj', (object,), {'data': 0})()
            self.txn_type = type('obj', (object,), {'data': ''})()
            self.status = type('obj', (object,), {'data': ''})()
            self.date_from = type('obj', (object,), {'data': None})()
            self.date_to = type('obj', (object,), {'data': None})()
            self.category_id = type('obj', (object,), {'data': 0})()
            self.partner_id = type('obj', (object,), {'data': 0})()
    
    class PaginatedResult:
        def __init__(self):
            self.items = []
            self.total = 0
            self.page = 1
            self.pages = 1
            self.has_prev = False
            self.has_next = False
            self.prev_num = 0
            self.next_num = 2
        
        def iter_pages(self, left_edge=1, right_edge=1, left_current=1, right_current=2):
            return range(1, min(4, self.pages + 1))
    
    return render_template('transactions/index.html', 
                         form=SearchForm(), 
                         transactions=PaginatedResult())

# Stub routes
@app.route('/transactions/create')
@login_required
def transactions_create():
    return "<h1>إنشاء معاملة جديدة - قيد التطوير</h1>"

@app.route('/transactions/transfer')
@login_required
def transactions_transfer():
    return "<h1>تحويل بين الخزائن - قيد التطوير</h1>"

@app.route('/reports/daily')
@login_required
def reports_daily():
    return "<h1>التقرير اليومي - قيد التطوير</h1>"

@app.route('/reports/monthly')
@login_required
def reports_monthly():
    return "<h1>التقرير الشهري - قيد التطوير</h1>"

@app.route('/reports/cashbox-balance')
@login_required
def reports_cashbox_balance():
    return "<h1>أرصدة الخزائن - قيد التطوير</h1>"

@app.route('/reports/by-category')
@login_required
def reports_by_category():
    return "<h1>تقرير حسب التصنيف - قيد التطوير</h1>"

@app.route('/reports/audit-log')
@login_required
def reports_audit_log():
    return "<h1>سجل النظام - قيد التطوير</h1>"

@app.route('/cashbox/<int:id>')
@login_required
def cashbox_view(id):
    return f"<h1>عرض الخزنة #{id} - قيد التطوير</h1>"

@app.route('/cashbox/create')
@login_required
def cashbox_create():
    return "<h1>إنشاء خزنة جديدة - قيد التطوير</h1>"

@app.route('/cashbox/<int:id>/edit')
@login_required
def cashbox_edit(id):
    return f"<h1>تعديل الخزنة #{id} - قيد التطوير</h1>"

@app.route('/transactions/<string:id>')
@login_required
def transactions_view(id):
    return f"<h1>عرض المعاملة #{id} - قيد التطوير</h1>"

@app.route('/auth/change-password')
@login_required
def auth_change_password():
    return "<h1>تغيير كلمة المرور - قيد التطوير</h1>"

@app.route('/profile')
@login_required
def main_profile():
    return "<h1>الملف الشخصي - قيد التطوير</h1>"

@app.template_filter('tojson')
def tojson_filter(obj):
    import json
    return json.dumps(obj)

# Health check endpoint for Render
@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
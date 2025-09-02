from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func, extract
from datetime import datetime, date, timedelta
from decimal import Decimal
from app import db
from app.models import CashBox, CashTransaction, Category, Partner

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Get all active cashboxes with balances
    cashboxes = CashBox.query.filter_by(is_active=True).all()
    cashbox_data = []
    total_balance = Decimal('0.00')
    
    for box in cashboxes:
        balance = box.current_balance
        today_change = box.today_balance_change
        cashbox_data.append({
            'box': box,
            'balance': balance,
            'today_change': today_change
        })
        total_balance += balance
    
    # Today's transactions summary
    today = date.today()
    today_txns = CashTransaction.query.filter(
        func.date(CashTransaction.date) == today,
        CashTransaction.status == 'approved'
    )
    
    today_receipts = today_txns.filter(
        CashTransaction.txn_type.in_(['receipt', 'transfer_in'])
    ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
    
    today_payments = today_txns.filter(
        CashTransaction.txn_type.in_(['payment', 'transfer_out'])
    ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
    
    # This month's summary
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    month_txns = CashTransaction.query.filter(
        extract('month', CashTransaction.date) == current_month,
        extract('year', CashTransaction.date) == current_year,
        CashTransaction.status == 'approved'
    )
    
    month_receipts = month_txns.filter(
        CashTransaction.txn_type == 'receipt'
    ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
    
    month_payments = month_txns.filter(
        CashTransaction.txn_type == 'payment'
    ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
    
    # Recent transactions
    recent_transactions = CashTransaction.query.order_by(
        CashTransaction.created_at.desc()
    ).limit(10).all()
    
    # Pending approvals count
    pending_count = CashTransaction.query.filter_by(status='draft').count()
    
    # Top categories this month
    top_expense_categories = db.session.query(
        Category,
        func.sum(CashTransaction.amount).label('total')
    ).join(
        CashTransaction
    ).filter(
        Category.category_type == 'expense',
        extract('month', CashTransaction.date) == current_month,
        extract('year', CashTransaction.date) == current_year,
        CashTransaction.status == 'approved',
        CashTransaction.txn_type == 'payment'
    ).group_by(Category.id).order_by(func.sum(CashTransaction.amount).desc()).limit(5).all()
    
    # Chart data for last 7 days
    chart_labels = []
    chart_receipts = []
    chart_payments = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%d/%m'))
        
        day_txns = CashTransaction.query.filter(
            func.date(CashTransaction.date) == day,
            CashTransaction.status == 'approved'
        )
        
        receipts = day_txns.filter(
            CashTransaction.txn_type == 'receipt'
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or 0
        
        payments = day_txns.filter(
            CashTransaction.txn_type == 'payment'
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or 0
        
        chart_receipts.append(float(receipts))
        chart_payments.append(float(payments))
    
    return render_template('dashboard.html',
        cashboxes=cashbox_data,
        total_balance=total_balance,
        today_receipts=today_receipts,
        today_payments=today_payments,
        month_receipts=month_receipts,
        month_payments=month_payments,
        recent_transactions=recent_transactions,
        pending_count=pending_count,
        top_expense_categories=top_expense_categories,
        chart_labels=chart_labels,
        chart_receipts=chart_receipts,
        chart_payments=chart_payments
    )

@main_bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)
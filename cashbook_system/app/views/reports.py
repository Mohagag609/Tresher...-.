from flask import Blueprint, render_template, request, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, extract, and_, case
from datetime import datetime, date, timedelta
from decimal import Decimal
import io
from app import db
from app.models import CashBox, CashTransaction, Category, Partner, AuditLog
from app.utils.decorators import permission_required

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/daily')
@login_required
@permission_required('can_view_reports')
def daily_report():
    # Get date from request or use today
    report_date = request.args.get('date', date.today().isoformat())
    if isinstance(report_date, str):
        report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
    
    cashbox_id = request.args.get('cashbox_id', type=int)
    
    # Build query
    query = CashTransaction.query.filter(
        func.date(CashTransaction.date) == report_date,
        CashTransaction.status == 'approved'
    )
    
    if cashbox_id:
        query = query.filter_by(cashbox_id=cashbox_id)
        cashbox = CashBox.query.get(cashbox_id)
    else:
        cashbox = None
    
    # Get transactions
    transactions = query.order_by(CashTransaction.voucher_no).all()
    
    # Calculate totals
    receipts = sum(t.amount for t in transactions if t.txn_type in ['receipt', 'transfer_in'])
    payments = sum(t.amount for t in transactions if t.txn_type in ['payment', 'transfer_out'])
    net = receipts - payments
    
    # Get cashboxes for filter
    cashboxes = CashBox.query.filter_by(is_active=True).all()
    
    return render_template('reports/daily.html',
        date=report_date,
        cashbox=cashbox,
        cashboxes=cashboxes,
        transactions=transactions,
        receipts=receipts,
        payments=payments,
        net=net
    )

@reports_bp.route('/monthly')
@login_required
@permission_required('can_view_reports')
def monthly_report():
    # Get month and year from request or use current
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    cashbox_id = request.args.get('cashbox_id', type=int)
    
    # Build query
    query = CashTransaction.query.filter(
        extract('month', CashTransaction.date) == month,
        extract('year', CashTransaction.date) == year,
        CashTransaction.status == 'approved'
    )
    
    if cashbox_id:
        query = query.filter_by(cashbox_id=cashbox_id)
        cashbox = CashBox.query.get(cashbox_id)
    else:
        cashbox = None
    
    # Group by day
    daily_summary = db.session.query(
        func.date(CashTransaction.date).label('date'),
        func.sum(case(
            (CashTransaction.txn_type.in_(['receipt', 'transfer_in']), CashTransaction.amount),
            else_=0
        )).label('receipts'),
        func.sum(case(
            (CashTransaction.txn_type.in_(['payment', 'transfer_out']), CashTransaction.amount),
            else_=0
        )).label('payments')
    ).filter(
        extract('month', CashTransaction.date) == month,
        extract('year', CashTransaction.date) == year,
        CashTransaction.status == 'approved'
    )
    
    if cashbox_id:
        daily_summary = daily_summary.filter(CashTransaction.cashbox_id == cashbox_id)
    
    daily_summary = daily_summary.group_by(func.date(CashTransaction.date)).order_by('date').all()
    
    # Calculate totals
    total_receipts = sum(day.receipts for day in daily_summary)
    total_payments = sum(day.payments for day in daily_summary)
    net = total_receipts - total_payments
    
    # Get cashboxes for filter
    cashboxes = CashBox.query.filter_by(is_active=True).all()
    
    return render_template('reports/monthly.html',
        month=month,
        year=year,
        cashbox=cashbox,
        cashboxes=cashboxes,
        daily_summary=daily_summary,
        total_receipts=total_receipts,
        total_payments=total_payments,
        net=net
    )

@reports_bp.route('/by-category')
@login_required
@permission_required('can_view_reports')
def by_category():
    # Get filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category_type = request.args.get('type', 'expense')
    
    # Build query
    query = db.session.query(
        Category,
        func.sum(CashTransaction.amount).label('total'),
        func.count(CashTransaction.id).label('count')
    ).join(
        CashTransaction
    ).filter(
        Category.category_type == category_type,
        CashTransaction.status == 'approved'
    )
    
    if date_from:
        query = query.filter(CashTransaction.date >= date_from)
    if date_to:
        query = query.filter(CashTransaction.date <= date_to)
    
    if category_type == 'income':
        query = query.filter(CashTransaction.txn_type == 'receipt')
    elif category_type == 'expense':
        query = query.filter(CashTransaction.txn_type == 'payment')
    
    categories = query.group_by(Category.id).order_by(func.sum(CashTransaction.amount).desc()).all()
    
    # Calculate total
    total = sum(cat.total for cat in categories)
    
    return render_template('reports/by_category.html',
        categories=categories,
        total=total,
        category_type=category_type,
        date_from=date_from,
        date_to=date_to
    )

@reports_bp.route('/by-partner')
@login_required
@permission_required('can_view_reports')
def by_partner():
    # Get filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    partner_type = request.args.get('type')
    
    # Build query
    query = db.session.query(
        Partner,
        func.sum(case(
            (CashTransaction.txn_type == 'receipt', CashTransaction.amount),
            else_=0
        )).label('receipts'),
        func.sum(case(
            (CashTransaction.txn_type == 'payment', CashTransaction.amount),
            else_=0
        )).label('payments'),
        func.count(CashTransaction.id).label('count')
    ).join(
        CashTransaction
    ).filter(
        CashTransaction.status == 'approved'
    )
    
    if date_from:
        query = query.filter(CashTransaction.date >= date_from)
    if date_to:
        query = query.filter(CashTransaction.date <= date_to)
    if partner_type:
        query = query.filter(Partner.partner_type == partner_type)
    
    partners = query.group_by(Partner.id).order_by((func.sum(CashTransaction.amount)).desc()).all()
    
    return render_template('reports/by_partner.html',
        partners=partners,
        partner_type=partner_type,
        date_from=date_from,
        date_to=date_to
    )

@reports_bp.route('/cashbox-balance')
@login_required
@permission_required('can_view_reports')
def cashbox_balance():
    cashboxes = CashBox.query.filter_by(is_active=True).all()
    
    balance_data = []
    total_balance = Decimal('0.00')
    
    for box in cashboxes:
        # Get today's movements
        today = date.today()
        today_txns = CashTransaction.query.filter(
            CashTransaction.cashbox_id == box.id,
            func.date(CashTransaction.date) == today,
            CashTransaction.status == 'approved'
        )
        
        today_receipts = today_txns.filter(
            CashTransaction.txn_type.in_(['receipt', 'transfer_in'])
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
        
        today_payments = today_txns.filter(
            CashTransaction.txn_type.in_(['payment', 'transfer_out'])
        ).with_entities(func.sum(CashTransaction.amount)).scalar() or Decimal('0.00')
        
        balance = box.current_balance
        
        balance_data.append({
            'cashbox': box,
            'opening_balance': box.opening_balance,
            'current_balance': balance,
            'today_receipts': today_receipts,
            'today_payments': today_payments,
            'today_net': today_receipts - today_payments
        })
        
        total_balance += balance
    
    return render_template('reports/cashbox_balance.html',
        balance_data=balance_data,
        total_balance=total_balance
    )

@reports_bp.route('/audit-log')
@login_required
@permission_required('can_view_reports')
def audit_log():
    page = request.args.get('page', 1, type=int)
    
    # Get filters
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Build query
    query = AuditLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter_by(action=action)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(AuditLog.created_at < date_to)
    
    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False
    )
    
    # Get users for filter
    from app.models import User
    users = User.query.all()
    
    # Get unique actions
    actions = db.session.query(AuditLog.action).distinct().all()
    actions = [a[0] for a in actions]
    
    return render_template('reports/audit_log.html',
        logs=logs,
        users=users,
        actions=actions,
        filters={
            'user_id': user_id,
            'action': action,
            'date_from': date_from,
            'date_to': date_to
        }
    )
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import case, extract
from app import db
from app.models import CashBox, CashTransaction, AuditLog
from app.forms import CashBoxForm
from app.utils.decorators import permission_required

cashbox_bp = Blueprint('cashbox', __name__)

@cashbox_bp.route('/')
@login_required
def index():
    cashboxes = CashBox.query.all()
    return render_template('cashbox/index.html', cashboxes=cashboxes)

@cashbox_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_cashbox')
def create():
    form = CashBoxForm()
    form.currency.choices = current_app.config['CURRENCIES']
    
    if form.validate_on_submit():
        cashbox = CashBox(
            code=form.code.data,
            name=form.name.data,
            name_ar=form.name_ar.data,
            box_type=form.box_type.data,
            currency=form.currency.data,
            opening_balance=form.opening_balance.data or 0,
            branch_name=form.branch_name.data,
            branch_code=form.branch_code.data,
            description=form.description.data,
            is_active=form.is_active.data
        )
        
        db.session.add(cashbox)
        
        # Log action
        AuditLog.log_action(
            user=current_user,
            action='create',
            model_name='CashBox',
            record_id=cashbox.code,
            new_values={'name': cashbox.name, 'opening_balance': str(cashbox.opening_balance)},
            description=f'Created cashbox: {cashbox.name}'
        )
        
        db.session.commit()
        flash(f'تم إنشاء الخزنة {cashbox.name} بنجاح', 'success')
        return redirect(url_for('cashbox.index'))
    
    return render_template('cashbox/form.html', form=form, title='إنشاء خزنة جديدة')

@cashbox_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_cashbox')
def edit(id):
    cashbox = CashBox.query.get_or_404(id)
    form = CashBoxForm(obj=cashbox)
    form.currency.choices = current_app.config['CURRENCIES']
    
    if form.validate_on_submit():
        old_values = {
            'name': cashbox.name,
            'opening_balance': str(cashbox.opening_balance),
            'is_active': cashbox.is_active
        }
        
        form.populate_obj(cashbox)
        
        # Log action
        AuditLog.log_action(
            user=current_user,
            action='update',
            model_name='CashBox',
            record_id=cashbox.code,
            old_values=old_values,
            new_values={
                'name': cashbox.name,
                'opening_balance': str(cashbox.opening_balance),
                'is_active': cashbox.is_active
            },
            description=f'Updated cashbox: {cashbox.name}'
        )
        
        db.session.commit()
        flash(f'تم تحديث الخزنة {cashbox.name} بنجاح', 'success')
        return redirect(url_for('cashbox.index'))
    
    return render_template('cashbox/form.html', form=form, title=f'تعديل خزنة: {cashbox.name}')

@cashbox_bp.route('/<int:id>')
@login_required
def view(id):
    cashbox = CashBox.query.get_or_404(id)
    
    # Get recent transactions
    recent_transactions = CashTransaction.query.filter_by(
        cashbox_id=cashbox.id
    ).order_by(CashTransaction.date.desc(), CashTransaction.created_at.desc()).limit(20).all()
    
    # Calculate statistics
    from sqlalchemy import func
    from datetime import datetime
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    month_stats = db.session.query(
        func.sum(case((CashTransaction.txn_type == 'receipt', CashTransaction.amount), else_=0)).label('receipts'),
        func.sum(case((CashTransaction.txn_type == 'payment', CashTransaction.amount), else_=0)).label('payments'),
        func.sum(case((CashTransaction.txn_type == 'transfer_in', CashTransaction.amount), else_=0)).label('transfers_in'),
        func.sum(case((CashTransaction.txn_type == 'transfer_out', CashTransaction.amount), else_=0)).label('transfers_out')
    ).filter(
        CashTransaction.cashbox_id == cashbox.id,
        CashTransaction.status == 'approved',
        extract('month', CashTransaction.date) == current_month,
        extract('year', CashTransaction.date) == current_year
    ).first()
    
    return render_template('cashbox/view.html',
        cashbox=cashbox,
        recent_transactions=recent_transactions,
        month_stats=month_stats
    )

@cashbox_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_cashbox')
def delete(id):
    cashbox = CashBox.query.get_or_404(id)
    
    # Check if cashbox has transactions
    if cashbox.transactions.count() > 0:
        flash('لا يمكن حذف خزنة بها معاملات', 'danger')
        return redirect(url_for('cashbox.index'))
    
    # Log action
    AuditLog.log_action(
        user=current_user,
        action='delete',
        model_name='CashBox',
        record_id=cashbox.code,
        old_values={'name': cashbox.name},
        description=f'Deleted cashbox: {cashbox.name}'
    )
    
    db.session.delete(cashbox)
    db.session.commit()
    
    flash(f'تم حذف الخزنة {cashbox.name} بنجاح', 'success')
    return redirect(url_for('cashbox.index'))
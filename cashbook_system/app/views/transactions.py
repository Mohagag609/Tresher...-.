from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid
from app import db
from app.models import CashTransaction, CashBox, Category, Partner, TransactionAttachment, AuditLog
from app.forms import TransactionForm, TransferForm, TransactionSearchForm
from app.utils.decorators import permission_required

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    form = TransactionSearchForm(request.args)
    
    # Build query
    query = CashTransaction.query
    
    # Apply filters
    if form.search.data:
        search = f'%{form.search.data}%'
        query = query.filter(
            db.or_(
                CashTransaction.voucher_no.like(search),
                CashTransaction.description.like(search),
                CashTransaction.reference_no.like(search)
            )
        )
    
    if form.cashbox_id.data:
        query = query.filter_by(cashbox_id=form.cashbox_id.data)
    
    if form.txn_type.data:
        query = query.filter_by(txn_type=form.txn_type.data)
    
    if form.status.data:
        query = query.filter_by(status=form.status.data)
    
    if form.category_id.data:
        query = query.filter_by(category_id=form.category_id.data)
    
    if form.partner_id.data:
        query = query.filter_by(partner_id=form.partner_id.data)
    
    if form.date_from.data:
        query = query.filter(CashTransaction.date >= form.date_from.data)
    
    if form.date_to.data:
        query = query.filter(CashTransaction.date <= form.date_to.data)
    
    # Populate select fields
    form.cashbox_id.choices = [(0, 'الكل')] + [(c.id, c.name) for c in CashBox.query.filter_by(is_active=True).all()]
    form.category_id.choices = [(0, 'الكل')] + [(c.id, c.name) for c in Category.query.filter_by(is_active=True).all()]
    form.partner_id.choices = [(0, 'الكل')] + [(p.id, p.name) for p in Partner.query.filter_by(is_active=True).all()]
    
    # Paginate
    transactions = query.order_by(
        CashTransaction.date.desc(),
        CashTransaction.created_at.desc()
    ).paginate(page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False)
    
    return render_template('transactions/index.html',
        transactions=transactions,
        form=form
    )

@transactions_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_draft')
def create():
    form = TransactionForm()
    
    # Populate select fields
    form.cashbox_id.choices = [(c.id, c.name) for c in CashBox.query.filter_by(is_active=True).all()]
    form.currency.choices = current_app.config['CURRENCIES']
    form.category_id.choices = [(0, '-- اختر --')] + [(c.id, c.name) for c in Category.query.filter_by(is_active=True).all()]
    form.partner_id.choices = [(0, '-- اختر --')] + [(p.id, p.name) for p in Partner.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        transaction = CashTransaction(
            cashbox_id=form.cashbox_id.data,
            txn_type=form.txn_type.data,
            date=form.date.data,
            amount=form.amount.data,
            currency=form.currency.data,
            category_id=form.category_id.data if form.category_id.data else None,
            partner_id=form.partner_id.data if form.partner_id.data else None,
            project_code=form.project_code.data,
            cost_center=form.cost_center.data,
            reference_no=form.reference_no.data,
            description=form.description.data,
            created_by_id=current_user.id,
            status='draft'
        )
        
        # Generate voucher number
        transaction.generate_voucher_no()
        
        db.session.add(transaction)
        db.session.flush()
        
        # Handle file upload
        if form.attachment.data:
            file = form.attachment.data
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                
                attachment = TransactionAttachment(
                    transaction_id=transaction.id,
                    filename=unique_filename,
                    original_filename=filename,
                    file_type=file.content_type,
                    file_size=os.path.getsize(file_path),
                    uploaded_by_id=current_user.id
                )
                db.session.add(attachment)
        
        # Auto-approve if requested and user has permission
        if 'submit_approve' in request.form and current_user.has_permission('can_approve'):
            try:
                transaction.approve(current_user)
                flash_msg = f'تم إنشاء واعتماد السند {transaction.voucher_no} بنجاح'
            except ValueError as e:
                flash(str(e), 'danger')
                db.session.rollback()
                return redirect(url_for('transactions.create'))
        else:
            flash_msg = f'تم إنشاء السند {transaction.voucher_no} بنجاح'
        
        # Log action
        AuditLog.log_action(
            user=current_user,
            action='create',
            model_name='CashTransaction',
            record_id=transaction.id,
            new_values={
                'voucher_no': transaction.voucher_no,
                'amount': str(transaction.amount),
                'type': transaction.txn_type
            },
            description=f'Created transaction: {transaction.voucher_no}'
        )
        
        db.session.commit()
        flash(flash_msg, 'success')
        return redirect(url_for('transactions.view', id=transaction.id))
    
    return render_template('transactions/form.html', form=form, title='إنشاء سند جديد')

@transactions_bp.route('/<string:id>')
@login_required
def view(id):
    transaction = CashTransaction.query.get_or_404(id)
    return render_template('transactions/view.html', transaction=transaction)

@transactions_bp.route('/<string:id>/approve', methods=['POST'])
@login_required
@permission_required('can_approve')
def approve(id):
    transaction = CashTransaction.query.get_or_404(id)
    
    try:
        transaction.approve(current_user)
        
        # If it's a transfer, approve the linked transaction
        if transaction.linked_txn and transaction.linked_txn.status == 'draft':
            transaction.linked_txn.approve(current_user)
        
        # Log action
        AuditLog.log_action(
            user=current_user,
            action='approve',
            model_name='CashTransaction',
            record_id=transaction.id,
            old_values={'status': 'draft'},
            new_values={'status': 'approved'},
            description=f'Approved transaction: {transaction.voucher_no}'
        )
        
        db.session.commit()
        flash(f'تم اعتماد السند {transaction.voucher_no} بنجاح', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    
    return redirect(url_for('transactions.view', id=id))

@transactions_bp.route('/<string:id>/void', methods=['GET', 'POST'])
@login_required
@permission_required('can_void')
def void(id):
    transaction = CashTransaction.query.get_or_404(id)
    
    if request.method == 'POST':
        reason = request.form.get('reason', '')
        
        if not reason:
            flash('يجب إدخال سبب الإلغاء', 'danger')
            return redirect(url_for('transactions.void', id=id))
        
        try:
            transaction.void(current_user, reason)
            
            # Log action
            AuditLog.log_action(
                user=current_user,
                action='void',
                model_name='CashTransaction',
                record_id=transaction.id,
                old_values={'status': 'approved'},
                new_values={'status': 'void', 'reason': reason},
                description=f'Voided transaction: {transaction.voucher_no}'
            )
            
            db.session.commit()
            flash(f'تم إلغاء السند {transaction.voucher_no} بنجاح', 'success')
            return redirect(url_for('transactions.view', id=id))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('transactions.view', id=id))
    
    return render_template('transactions/void.html', transaction=transaction)

@transactions_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
@permission_required('can_create_draft')
def transfer():
    form = TransferForm()
    
    # Populate select fields
    cashboxes = CashBox.query.filter_by(is_active=True).all()
    form.from_cashbox_id.choices = [(c.id, f'{c.name} ({c.currency})') for c in cashboxes]
    form.to_cashbox_id.choices = [(c.id, f'{c.name} ({c.currency})') for c in cashboxes]
    
    if form.validate_on_submit():
        from_box = CashBox.query.get(form.from_cashbox_id.data)
        to_box = CashBox.query.get(form.to_cashbox_id.data)
        
        try:
            out_txn, in_txn = CashTransaction.create_transfer(
                from_box=from_box,
                to_box=to_box,
                amount=form.amount.data,
                user=current_user,
                description=form.description.data,
                date=form.date.data
            )
            
            # Auto-approve if user has permission
            if current_user.has_permission('can_approve'):
                out_txn.approve(current_user)
                in_txn.approve(current_user)
            
            # Log action
            AuditLog.log_action(
                user=current_user,
                action='transfer',
                model_name='CashTransaction',
                record_id=out_txn.id,
                new_values={
                    'from': from_box.name,
                    'to': to_box.name,
                    'amount': str(form.amount.data)
                },
                description=f'Transfer from {from_box.name} to {to_box.name}'
            )
            
            db.session.commit()
            flash(f'تم التحويل من {from_box.name} إلى {to_box.name} بنجاح', 'success')
            return redirect(url_for('transactions.view', id=out_txn.id))
            
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
    
    return render_template('transactions/transfer.html', form=form)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
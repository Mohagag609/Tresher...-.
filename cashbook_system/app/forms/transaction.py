from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, DecimalField, SelectField, TextAreaField, DateField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional, NumberRange, ValidationError
from datetime import datetime
from decimal import Decimal

class TransactionForm(FlaskForm):
    cashbox_id = SelectField('الخزنة', coerce=int, validators=[DataRequired()])
    txn_type = SelectField('نوع العملية', choices=[
        ('receipt', 'قبض (إيراد)'),
        ('payment', 'صرف (مصروف)')
    ], validators=[DataRequired()])
    
    date = DateField('التاريخ', format='%Y-%m-%d', 
                     default=datetime.today, validators=[DataRequired()])
    
    amount = DecimalField('المبلغ', places=2, validators=[
        DataRequired(),
        NumberRange(min=0.01, message='المبلغ يجب أن يكون أكبر من صفر')
    ])
    
    currency = SelectField('العملة', choices=[], default='EGP')
    
    category_id = SelectField('التصنيف', coerce=int, validators=[Optional()])
    partner_id = SelectField('الشريك', coerce=int, validators=[Optional()])
    
    project_code = StringField('كود المشروع', validators=[Optional()])
    cost_center = StringField('مركز التكلفة', validators=[Optional()])
    
    reference_no = StringField('رقم المرجع', validators=[Optional()])
    description = TextAreaField('الوصف', validators=[Optional()])
    
    attachment = FileField('المرفقات', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx'], 
                   'الملفات المسموحة: jpg, png, pdf, doc, docx')
    ])
    
    submit = SubmitField('حفظ')
    submit_approve = SubmitField('حفظ واعتماد')
    
    def validate_amount(self, field):
        if field.data and field.data <= 0:
            raise ValidationError('المبلغ يجب أن يكون أكبر من صفر')

class TransferForm(FlaskForm):
    from_cashbox_id = SelectField('من خزنة', coerce=int, validators=[DataRequired()])
    to_cashbox_id = SelectField('إلى خزنة', coerce=int, validators=[DataRequired()])
    
    date = DateField('التاريخ', format='%Y-%m-%d',
                     default=datetime.today, validators=[DataRequired()])
    
    amount = DecimalField('المبلغ', places=2, validators=[
        DataRequired(),
        NumberRange(min=0.01, message='المبلغ يجب أن يكون أكبر من صفر')
    ])
    
    description = TextAreaField('الوصف', validators=[Optional()])
    
    submit = SubmitField('تحويل')
    
    def validate(self, **kwargs):
        if not super().validate(**kwargs):
            return False
        
        if self.from_cashbox_id.data == self.to_cashbox_id.data:
            self.to_cashbox_id.errors.append('لا يمكن التحويل لنفس الخزنة')
            return False
        
        return True

class TransactionSearchForm(FlaskForm):
    search = StringField('بحث', validators=[Optional()])
    cashbox_id = SelectField('الخزنة', coerce=int, validators=[Optional()])
    txn_type = SelectField('نوع العملية', choices=[
        ('', 'الكل'),
        ('receipt', 'قبض'),
        ('payment', 'صرف'),
        ('transfer_in', 'تحويل وارد'),
        ('transfer_out', 'تحويل صادر')
    ], validators=[Optional()])
    
    status = SelectField('الحالة', choices=[
        ('', 'الكل'),
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('void', 'ملغي')
    ], validators=[Optional()])
    
    category_id = SelectField('التصنيف', coerce=int, validators=[Optional()])
    partner_id = SelectField('الشريك', coerce=int, validators=[Optional()])
    
    date_from = DateField('من تاريخ', format='%Y-%m-%d', validators=[Optional()])
    date_to = DateField('إلى تاريخ', format='%Y-%m-%d', validators=[Optional()])
    
    submit = SubmitField('بحث')
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError
from app.models import Partner

class PartnerForm(FlaskForm):
    code = StringField('الكود', validators=[Optional(), Length(max=20)])
    
    name = StringField('الاسم', validators=[
        DataRequired(),
        Length(max=150, message='الاسم يجب ألا يتجاوز 150 حرف')
    ])
    
    name_ar = StringField('الاسم بالعربية', validators=[Optional()])
    
    partner_type = SelectField('النوع', choices=[
        ('customer', 'عميل'),
        ('supplier', 'مورد'),
        ('employee', 'موظف'),
        ('other', 'أخرى')
    ], default='other', validators=[DataRequired()])
    
    # Contact info
    phone = StringField('الهاتف', validators=[Optional(), Length(max=30)])
    mobile = StringField('الموبايل', validators=[Optional(), Length(max=30)])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Email()])
    address = TextAreaField('العنوان', validators=[Optional()])
    
    # Financial info
    tax_number = StringField('الرقم الضريبي', validators=[Optional(), Length(max=50)])
    commercial_register = StringField('السجل التجاري', validators=[Optional(), Length(max=50)])
    
    # Bank info
    bank_name = StringField('اسم البنك', validators=[Optional(), Length(max=100)])
    bank_account = StringField('رقم الحساب', validators=[Optional(), Length(max=50)])
    bank_branch = StringField('الفرع', validators=[Optional(), Length(max=100)])
    
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    is_active = BooleanField('نشط', default=True)
    
    submit = SubmitField('حفظ')
    
    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, obj=obj, **kwargs)
        self.original_code = obj.code if obj else None
    
    def validate_code(self, field):
        if field.data and field.data != self.original_code:
            partner = Partner.query.filter_by(code=field.data).first()
            if partner:
                raise ValidationError('هذا الكود مستخدم بالفعل')
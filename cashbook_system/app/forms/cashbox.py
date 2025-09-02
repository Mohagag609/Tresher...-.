from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, SelectField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from app.models import CashBox

class CashBoxForm(FlaskForm):
    code = StringField('الكود', validators=[
        DataRequired(),
        Length(max=10, message='الكود يجب ألا يتجاوز 10 أحرف')
    ])
    
    name = StringField('الاسم', validators=[
        DataRequired(),
        Length(max=100, message='الاسم يجب ألا يتجاوز 100 حرف')
    ])
    
    name_ar = StringField('الاسم بالعربية', validators=[Optional()])
    
    box_type = SelectField('نوع الخزنة', choices=[
        ('main', 'رئيسية'),
        ('branch', 'فرع'),
        ('petty', 'عهدة')
    ], default='main', validators=[DataRequired()])
    
    currency = SelectField('العملة', choices=[], default='EGP', validators=[DataRequired()])
    
    opening_balance = DecimalField('الرصيد الافتتاحي', places=2, default=0.00, 
                                  validators=[Optional()])
    
    branch_name = StringField('اسم الفرع', validators=[Optional()])
    branch_code = StringField('كود الفرع', validators=[Optional()])
    
    description = TextAreaField('الوصف', validators=[Optional()])
    
    is_active = BooleanField('نشط', default=True)
    
    submit = SubmitField('حفظ')
    
    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, obj=obj, **kwargs)
        self.original_code = obj.code if obj else None
    
    def validate_code(self, field):
        if field.data != self.original_code:
            cashbox = CashBox.query.filter_by(code=field.data).first()
            if cashbox:
                raise ValidationError('هذا الكود مستخدم بالفعل')
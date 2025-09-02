from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, TextAreaField, BooleanField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from app.models import Category

class CategoryForm(FlaskForm):
    code = StringField('الكود', validators=[Optional(), Length(max=20)])
    
    name = StringField('الاسم', validators=[
        DataRequired(),
        Length(max=120, message='الاسم يجب ألا يتجاوز 120 حرف')
    ])
    
    name_ar = StringField('الاسم بالعربية', validators=[Optional()])
    
    category_type = SelectField('النوع', choices=[
        ('income', 'إيراد'),
        ('expense', 'مصروف'),
        ('transfer', 'تحويل')
    ], validators=[DataRequired()])
    
    parent_id = SelectField('التصنيف الأب', coerce=int, validators=[Optional()])
    
    # Display
    icon = StringField('الأيقونة', validators=[Optional(), Length(max=50)])
    color = StringField('اللون', validators=[Optional(), Length(max=7)])
    display_order = IntegerField('ترتيب العرض', default=0, validators=[Optional()])
    
    # Budget
    monthly_budget = DecimalField('الميزانية الشهرية', places=2, validators=[Optional()])
    yearly_budget = DecimalField('الميزانية السنوية', places=2, validators=[Optional()])
    
    description = TextAreaField('الوصف', validators=[Optional()])
    
    is_active = BooleanField('نشط', default=True)
    
    submit = SubmitField('حفظ')
    
    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, obj=obj, **kwargs)
        self.original_code = obj.code if obj else None
    
    def validate_code(self, field):
        if field.data and field.data != self.original_code:
            category = Category.query.filter_by(code=field.data).first()
            if category:
                raise ValidationError('هذا الكود مستخدم بالفعل')
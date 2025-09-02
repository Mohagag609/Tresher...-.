from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import User

class LoginForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    remember_me = BooleanField('تذكرني')
    submit = SubmitField('تسجيل الدخول')

class RegisterForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[
        DataRequired(),
        Length(min=3, max=80, message='يجب أن يكون اسم المستخدم بين 3 و 80 حرف')
    ])
    email = StringField('البريد الإلكتروني', validators=[
        DataRequired(),
        Email(message='بريد إلكتروني غير صحيح')
    ])
    full_name = StringField('الاسم الكامل', validators=[DataRequired()])
    full_name_ar = StringField('الاسم الكامل بالعربية')
    phone = StringField('رقم الهاتف')
    password = PasswordField('كلمة المرور', validators=[
        DataRequired(),
        Length(min=6, message='كلمة المرور يجب أن تكون 6 أحرف على الأقل')
    ])
    password2 = PasswordField('تأكيد كلمة المرور', validators=[
        DataRequired(),
        EqualTo('password', message='كلمات المرور غير متطابقة')
    ])
    submit = SubmitField('تسجيل')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('اسم المستخدم مستخدم بالفعل')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('البريد الإلكتروني مستخدم بالفعل')

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('كلمة المرور الحالية', validators=[DataRequired()])
    new_password = PasswordField('كلمة المرور الجديدة', validators=[
        DataRequired(),
        Length(min=6, message='كلمة المرور يجب أن تكون 6 أحرف على الأقل')
    ])
    new_password2 = PasswordField('تأكيد كلمة المرور الجديدة', validators=[
        DataRequired(),
        EqualTo('new_password', message='كلمات المرور غير متطابقة')
    ])
    submit = SubmitField('تغيير كلمة المرور')
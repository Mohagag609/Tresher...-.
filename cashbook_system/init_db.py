#!/usr/bin/env python
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models import User, Role, CashBox, Category, Partner
from datetime import datetime

def init_database():
    """Initialize database with default data"""
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✓ تم إنشاء جداول قاعدة البيانات")
        
        # Create default roles
        roles_data = [
            {
                'name': 'admin',
                'name_ar': 'مدير النظام',
                'description': 'صلاحيات كاملة على النظام',
                'can_create_draft': True,
                'can_approve': True,
                'can_void': True,
                'can_manage_cashbox': True,
                'can_manage_users': True,
                'can_view_reports': True,
                'can_export': True,
                'can_close_period': True
            },
            {
                'name': 'approver',
                'name_ar': 'معتمد',
                'description': 'يمكنه اعتماد وإلغاء السندات',
                'can_create_draft': True,
                'can_approve': True,
                'can_void': True,
                'can_manage_cashbox': False,
                'can_manage_users': False,
                'can_view_reports': True,
                'can_export': True,
                'can_close_period': False
            },
            {
                'name': 'cashier',
                'name_ar': 'أمين الصندوق',
                'description': 'يمكنه إنشاء السندات فقط',
                'can_create_draft': True,
                'can_approve': False,
                'can_void': False,
                'can_manage_cashbox': False,
                'can_manage_users': False,
                'can_view_reports': True,
                'can_export': False,
                'can_close_period': False
            },
            {
                'name': 'auditor',
                'name_ar': 'مراجع',
                'description': 'يمكنه عرض التقارير فقط',
                'can_create_draft': False,
                'can_approve': False,
                'can_void': False,
                'can_manage_cashbox': False,
                'can_manage_users': False,
                'can_view_reports': True,
                'can_export': True,
                'can_close_period': False
            }
        ]
        
        for role_data in roles_data:
            if not Role.query.filter_by(name=role_data['name']).first():
                role = Role(**role_data)
                db.session.add(role)
        
        db.session.commit()
        print("✓ تم إنشاء الأدوار الافتراضية")
        
        # Create admin user
        if not User.query.filter_by(username='admin').first():
            admin_role = Role.query.filter_by(name='admin').first()
            admin = User(
                username='admin',
                email='admin@cashbook.com',
                full_name='مدير النظام',
                full_name_ar='مدير النظام',
                is_active=True,
                is_superuser=True,
                role=admin_role
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✓ تم إنشاء المستخدم الرئيسي (admin/admin123)")
        
        # Create demo user
        if not User.query.filter_by(username='demo').first():
            cashier_role = Role.query.filter_by(name='cashier').first()
            demo = User(
                username='demo',
                email='demo@cashbook.com',
                full_name='مستخدم تجريبي',
                full_name_ar='مستخدم تجريبي',
                is_active=True,
                role=cashier_role
            )
            demo.set_password('demo123')
            db.session.add(demo)
            db.session.commit()
            print("✓ تم إنشاء المستخدم التجريبي (demo/demo123)")
        
        # Create default cashboxes
        cashboxes_data = [
            {
                'code': 'MAIN',
                'name': 'Main Cash Box',
                'name_ar': 'الخزنة الرئيسية',
                'box_type': 'main',
                'currency': 'EGP',
                'opening_balance': 10000.00,
                'description': 'الخزنة الرئيسية للشركة',
                'is_active': True
            },
            {
                'code': 'PETTY',
                'name': 'Petty Cash',
                'name_ar': 'العهدة النثرية',
                'box_type': 'petty',
                'currency': 'EGP',
                'opening_balance': 2000.00,
                'description': 'عهدة المصروفات النثرية',
                'is_active': True
            },
            {
                'code': 'BANK',
                'name': 'Bank Account',
                'name_ar': 'الحساب البنكي',
                'box_type': 'main',
                'currency': 'EGP',
                'opening_balance': 50000.00,
                'description': 'الحساب البنكي الرئيسي',
                'is_active': True
            }
        ]
        
        for box_data in cashboxes_data:
            if not CashBox.query.filter_by(code=box_data['code']).first():
                cashbox = CashBox(**box_data)
                db.session.add(cashbox)
        
        db.session.commit()
        print("✓ تم إنشاء الخزائن الافتراضية")
        
        # Create default categories
        categories_data = [
            # Income categories
            {'code': 'SALES', 'name': 'Sales', 'name_ar': 'المبيعات', 'category_type': 'income', 'color': '#10b981'},
            {'code': 'SERVICE', 'name': 'Services', 'name_ar': 'الخدمات', 'category_type': 'income', 'color': '#06b6d4'},
            {'code': 'OTHER_INC', 'name': 'Other Income', 'name_ar': 'إيرادات أخرى', 'category_type': 'income', 'color': '#8b5cf6'},
            
            # Expense categories
            {'code': 'SALARY', 'name': 'Salaries', 'name_ar': 'الرواتب', 'category_type': 'expense', 'color': '#ef4444'},
            {'code': 'RENT', 'name': 'Rent', 'name_ar': 'الإيجار', 'category_type': 'expense', 'color': '#f59e0b'},
            {'code': 'UTILITIES', 'name': 'Utilities', 'name_ar': 'المرافق', 'category_type': 'expense', 'color': '#ec4899'},
            {'code': 'SUPPLIES', 'name': 'Office Supplies', 'name_ar': 'مستلزمات مكتبية', 'category_type': 'expense', 'color': '#a855f7'},
            {'code': 'TRANSPORT', 'name': 'Transportation', 'name_ar': 'المواصلات', 'category_type': 'expense', 'color': '#3b82f6'},
            {'code': 'MARKETING', 'name': 'Marketing', 'name_ar': 'التسويق', 'category_type': 'expense', 'color': '#14b8a6'},
            {'code': 'OTHER_EXP', 'name': 'Other Expenses', 'name_ar': 'مصروفات أخرى', 'category_type': 'expense', 'color': '#6b7280'},
            
            # Transfer category
            {'code': 'TRANSFER', 'name': 'Transfer', 'name_ar': 'تحويل', 'category_type': 'transfer', 'color': '#0ea5e9'}
        ]
        
        for cat_data in categories_data:
            if not Category.query.filter_by(code=cat_data['code']).first():
                category = Category(**cat_data)
                db.session.add(category)
        
        db.session.commit()
        print("✓ تم إنشاء التصنيفات الافتراضية")
        
        # Create sample partners
        partners_data = [
            {
                'code': 'CUST001',
                'name': 'Ahmed Mohamed',
                'name_ar': 'أحمد محمد',
                'partner_type': 'customer',
                'phone': '01012345678',
                'email': 'ahmed@example.com',
                'is_active': True
            },
            {
                'code': 'SUPP001',
                'name': 'ABC Company',
                'name_ar': 'شركة أي بي سي',
                'partner_type': 'supplier',
                'phone': '0223456789',
                'email': 'info@abc.com',
                'is_active': True
            },
            {
                'code': 'EMP001',
                'name': 'Mohamed Ali',
                'name_ar': 'محمد علي',
                'partner_type': 'employee',
                'phone': '01098765432',
                'email': 'mohamed@company.com',
                'is_active': True
            }
        ]
        
        for partner_data in partners_data:
            if not Partner.query.filter_by(code=partner_data['code']).first():
                partner = Partner(**partner_data)
                db.session.add(partner)
        
        db.session.commit()
        print("✓ تم إنشاء الشركاء الافتراضيين")
        
        print("\n" + "="*50)
        print("تم إعداد قاعدة البيانات بنجاح!")
        print("="*50)
        print("\nبيانات الدخول:")
        print("  المدير: admin / admin123")
        print("  تجريبي: demo / demo123")
        print("\nلتشغيل البرنامج:")
        print("  python run.py")
        print("="*50)

if __name__ == '__main__':
    init_database()
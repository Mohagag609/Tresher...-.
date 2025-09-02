# 💰 نظام إدارة الخزينة الاحترافي
## Professional Cash Management System

نظام متكامل لإدارة الخزينة والمعاملات المالية مبني بـ Python Flask مع واجهة عصرية باستخدام TailwindCSS.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.0-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ المميزات الرئيسية

### 📊 إدارة الخزائن
- ✅ خزائن متعددة (رئيسية/فرعية/عهدة)
- ✅ دعم العملات المتعددة
- ✅ تتبع الأرصدة اللحظية
- ✅ التحويلات بين الخزائن

### 📝 المعاملات المالية
- ✅ سندات قبض وصرف
- ✅ ترقيم تلقائي للسندات
- ✅ نظام اعتماد متعدد المراحل (مسودة → معتمد → ملغي)
- ✅ إرفاق المستندات والفواتير

### 👥 إدارة الشركاء
- ✅ عملاء وموردين وموظفين
- ✅ تتبع المعاملات لكل شريك
- ✅ كشف حساب تفصيلي

### 📈 التقارير المتقدمة
- ✅ تقرير يومي وشهري
- ✅ تقارير حسب التصنيف والشريك
- ✅ أرصدة الخزائن
- ✅ تصدير Excel/PDF
- ✅ رسوم بيانية تفاعلية

### 🔐 الأمان والصلاحيات
- ✅ نظام صلاحيات متقدم (4 مستويات)
- ✅ سجل تدقيق كامل (Audit Log)
- ✅ تشفير كلمات المرور
- ✅ جلسات آمنة

## 🚀 التثبيت السريع

### 1️⃣ استنساخ المشروع
```bash
cd /workspace/cashbook_system
```

### 2️⃣ إنشاء البيئة الافتراضية
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# أو
venv\Scripts\activate  # Windows
```

### 3️⃣ تثبيت المتطلبات
```bash
pip install -r requirements.txt
```

### 4️⃣ إعداد قاعدة البيانات
```bash
python init_db.py
```

### 5️⃣ تشغيل البرنامج
```bash
python run.py
```

البرنامج سيعمل على: http://localhost:5000

## 👤 بيانات الدخول الافتراضية

| المستخدم | كلمة المرور | الصلاحيات |
|---------|------------|----------|
| admin   | admin123   | مدير النظام (كل الصلاحيات) |
| demo    | demo123    | أمين صندوق (إنشاء سندات فقط) |

## 📁 هيكل المشروع

```
cashbook_system/
├── app/
│   ├── __init__.py          # تهيئة التطبيق
│   ├── models/              # نماذج قاعدة البيانات
│   │   ├── user.py          # المستخدمين والأدوار
│   │   ├── cashbox.py       # الخزائن
│   │   ├── transaction.py   # المعاملات
│   │   ├── category.py      # التصنيفات
│   │   ├── partner.py       # الشركاء
│   │   └── audit.py         # سجل التدقيق
│   ├── views/               # معالجات الطلبات
│   │   ├── auth.py          # المصادقة
│   │   ├── main.py          # الصفحة الرئيسية
│   │   ├── cashbox.py       # إدارة الخزائن
│   │   ├── transactions.py  # المعاملات
│   │   └── reports.py       # التقارير
│   ├── forms/               # نماذج الإدخال
│   ├── templates/           # قوالب HTML
│   │   ├── base.html        # القالب الأساسي
│   │   ├── dashboard.html   # لوحة التحكم
│   │   └── ...
│   ├── static/              # الملفات الثابتة
│   └── utils/               # أدوات مساعدة
├── instance/                # قاعدة البيانات
├── migrations/              # ترحيلات قاعدة البيانات
├── config.py               # إعدادات التطبيق
├── requirements.txt        # المتطلبات
├── init_db.py             # إعداد قاعدة البيانات
└── run.py                 # نقطة البداية
```

## 🔧 الإعدادات المتقدمة

### تغيير قاعدة البيانات
لاستخدام PostgreSQL بدلاً من SQLite، قم بتعديل `config.py`:

```python
SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/cashbook'
```

### تفعيل HTTPS
في بيئة الإنتاج، قم بتعديل `config.py`:

```python
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
```

## 📊 لقطات الشاشة

### لوحة التحكم
- عرض شامل للأرصدة والحركات
- رسوم بيانية تفاعلية
- إحصائيات لحظية

### إدارة المعاملات
- إنشاء سندات قبض وصرف
- نظام اعتماد متعدد المراحل
- البحث والتصفية المتقدمة

### التقارير
- تقارير يومية وشهرية
- تصدير Excel/PDF
- رسوم بيانية تحليلية

## 🎯 حالات الاستخدام

1. **الشركات الصغيرة والمتوسطة**: إدارة النقدية اليومية
2. **المحلات التجارية**: تتبع المبيعات والمصروفات
3. **المؤسسات الخيرية**: إدارة التبرعات والصرف
4. **المكاتب الإدارية**: إدارة العهد والمصروفات النثرية

## 🛠️ التطوير والتخصيص

### إضافة تصنيف جديد
```python
# في app/models/category.py
new_category = Category(
    code='NEW_CAT',
    name='New Category',
    name_ar='تصنيف جديد',
    category_type='expense'
)
db.session.add(new_category)
db.session.commit()
```

### إضافة عملة جديدة
```python
# في config.py
CURRENCIES = [
    ('EGP', 'جنيه مصري'),
    ('USD', 'دولار أمريكي'),
    ('EUR', 'يورو'),
    ('AED', 'درهم إماراتي')  # عملة جديدة
]
```

## 📝 الترخيص

هذا المشروع مرخص تحت رخصة MIT - انظر ملف [LICENSE](LICENSE) للتفاصيل.

## 🤝 المساهمة

نرحب بالمساهمات! يرجى:
1. Fork المشروع
2. إنشاء فرع جديد (`git checkout -b feature/AmazingFeature`)
3. Commit التغييرات (`git commit -m 'Add some AmazingFeature'`)
4. Push إلى الفرع (`git push origin feature/AmazingFeature`)
5. فتح Pull Request

## 📞 الدعم والتواصل

- 📧 Email: support@cashbook.com
- 💬 Discord: [Join our server](https://discord.gg/cashbook)
- 📖 Documentation: [docs.cashbook.com](https://docs.cashbook.com)

## 🌟 شكر خاص

شكراً لكل من ساهم في تطوير هذا النظام وجعله أفضل!

---

**صُنع بـ ❤️ بواسطة فريق التطوير**
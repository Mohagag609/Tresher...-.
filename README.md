# 🏦 نظام إدارة الخزينة الاحترافي
## Professional Cash Management System

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Production-success)

نظام احترافي متكامل لإدارة الخزينة والمعاملات المالية بواجهة عصرية وتصميم متجاوب.

## ✨ المميزات الرئيسية

### 📊 إدارة الخزائن
- ✅ خزائن متعددة (رئيسية، فرعية، بنكية)
- ✅ حساب الأرصدة التلقائي
- ✅ تحويلات بين الخزائن
- ✅ إغلاق الفترات المحاسبية

### 💰 المعاملات المالية
- ✅ سندات قبض وصرف
- ✅ ترقيم تلقائي حسب السنة والخزنة
- ✅ نظام اعتماد ثلاثي (Draft → Approved → Void)
- ✅ ربط المعاملات بالتصنيفات والشركاء

### 👥 نظام الصلاحيات
- ✅ **Admin**: كل الصلاحيات
- ✅ **Approver**: اعتماد وإلغاء المعاملات
- ✅ **Cashier**: إنشاء المعاملات
- ✅ **Auditor**: عرض التقارير فقط

### 📈 التقارير والإحصائيات
- ✅ لوحة تحكم تفاعلية
- ✅ تقارير يومية وشهرية
- ✅ تقارير حسب التصنيف والشريك
- ✅ سجل مراجعة كامل (Audit Log)

### 🎨 التصميم والواجهة
- ✅ تصميم عصري ومتجاوب
- ✅ واجهة عربية بالكامل
- ✅ دعم RTL كامل
- ✅ رسوم متحركة سلسة
- ✅ ألوان متدرجة احترافية

## 🚀 التثبيت والتشغيل

### المتطلبات
- Python 3.9+
- SQLite3

### التثبيت المحلي
```bash
# استنساخ المشروع
git clone https://github.com/yourusername/cashbook-professional.git
cd cashbook-professional

# تثبيت المكتبات
pip install -r requirements.txt

# تشغيل التطبيق
python app.py
```

التطبيق سيعمل على: http://localhost:5000

## 👤 بيانات الدخول الافتراضية

| المستخدم | اسم المستخدم | كلمة المرور | الصلاحيات |
|----------|--------------|-------------|-----------|
| مدير النظام | admin | admin123 | كل الصلاحيات |
| المعتمد | approver | approver123 | اعتماد المعاملات |
| أمين الصندوق | cashier | cashier123 | إنشاء المعاملات |
| المراجع | auditor | auditor123 | عرض التقارير |

## 📦 هيكل قاعدة البيانات

### الجداول الرئيسية
- **users**: المستخدمين والصلاحيات
- **cashboxes**: الخزائن
- **transactions**: المعاملات المالية
- **categories**: التصنيفات
- **partners**: الشركاء (عملاء/موردين)
- **audit_log**: سجل المراجعة
- **period_closes**: إغلاق الفترات

## 🌐 النشر على Render

1. ارفع المشروع على GitHub
2. اربط المستودع بـ Render
3. استخدم الإعدادات التالية:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`

## 📱 الصفحات المتاحة

- `/` - الصفحة الرئيسية
- `/login` - تسجيل الدخول
- `/dashboard` - لوحة التحكم
- `/transactions` - المعاملات
- `/transactions/new` - معاملة جديدة
- `/transfers/new` - تحويل بين الخزائن
- `/cashboxes` - الخزائن
- `/partners` - الشركاء
- `/categories` - التصنيفات
- `/reports` - التقارير

## 🛠️ التقنيات المستخدمة

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: Bootstrap 5 RTL
- **Icons**: Font Awesome 6
- **Animations**: Animate.css
- **Alerts**: SweetAlert2
- **Fonts**: Google Fonts (Cairo)

## 📄 الترخيص

هذا المشروع مرخص تحت رخصة MIT

## 👨‍💻 المطور

تم تطوير هذا النظام بواسطة فريق التطوير الاحترافي

---

**© 2024 نظام إدارة الخزينة الاحترافي - جميع الحقوق محفوظة**
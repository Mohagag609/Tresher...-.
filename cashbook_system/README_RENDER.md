# 🚀 نشر نظام الخزينة على Render

## خطوات النشر على Render:

### 1️⃣ **رفع الكود على GitHub**

```bash
cd /workspace/cashbook_system
git init
git add .
git commit -m "Initial commit - Cash Management System"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/cashbook-system.git
git push -u origin main
```

### 2️⃣ **إنشاء حساب على Render**

1. اذهب إلى [render.com](https://render.com)
2. سجل حساب جديد (مجاني)
3. اربط حسابك بـ GitHub

### 3️⃣ **إنشاء Web Service جديد**

1. اضغط على **New +** > **Web Service**
2. اختر **Connect a repository**
3. اختر مستودع `cashbook-system`
4. املأ الإعدادات:

```
Name: cashbook-system
Region: Frankfurt (EU Central)
Branch: main
Runtime: Python 3
Build Command: ./build.sh
Start Command: gunicorn run_render:app
Instance Type: Free
```

### 4️⃣ **إضافة Environment Variables**

في قسم **Environment**، أضف:

```
SECRET_KEY = [اضغط Generate لإنشاء مفتاح عشوائي]
PYTHON_VERSION = 3.11.0
```

### 5️⃣ **النشر**

1. اضغط **Create Web Service**
2. انتظر حتى ينتهي Build (5-10 دقائق)
3. البرنامج سيعمل على: `https://cashbook-system.onrender.com`

## 📝 **ملاحظات مهمة:**

### ⚠️ **قاعدة البيانات**

- النسخة المجانية تستخدم SQLite (محلية)
- البيانات ستُحذف عند كل deploy جديد
- للحفاظ على البيانات، استخدم PostgreSQL:

```python
# في render.yaml أضف:
databases:
  - name: cashbook-db
    databaseName: cashbook
    user: cashbook
    plan: free

# وغير DATABASE_URL إلى:
DATABASE_URL = postgresql://...
```

### 🔒 **الأمان**

1. غيّر `SECRET_KEY` في Production
2. غيّر كلمات المرور الافتراضية
3. فعّل HTTPS (تلقائي في Render)

### 🔄 **التحديثات**

```bash
git add .
git commit -m "Update"
git push origin main
```

Render سيعيد النشر تلقائياً!

## 🎯 **بيانات الدخول الافتراضية:**

- **المدير:** admin / admin123
- **تجريبي:** demo / demo123

## 🆘 **حل المشاكل:**

### إذا فشل Build:
1. تأكد من `build.sh` executable
2. تأكد من `requirements.txt` صحيح
3. راجع Logs في Render Dashboard

### إذا لم يعمل الموقع:
1. تأكد من Port binding: `${PORT}`
2. تأكد من gunicorn مثبت
3. راجع Runtime Logs

## 📊 **مراقبة الأداء:**

Render يوفر:
- Metrics (CPU, Memory)
- Logs في الوقت الفعلي
- Health checks تلقائية
- تنبيهات بالإيميل

## 🚀 **ترقية الخطة:**

للحصول على:
- قاعدة بيانات دائمة
- نطاق خاص (custom domain)
- أداء أفضل
- Auto-scaling

ترقى إلى Starter ($7/شهر) أو Professional

---

**النظام جاهز للنشر! 🎉**
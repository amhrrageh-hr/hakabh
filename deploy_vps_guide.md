# 🚀 دليل نشر مشروع "هكبة المليون" وربط السيرفر وتطبيق سطح المكتب

هذا الدليل الشامل يشرح جميع الأوامر والخطوات اللازمة لتشغيل الموقع الإلكتروني على سيرفر خارجي (VPS) يعمل 24 ساعة بدون انقطاع، مع ربط تطبيق سطح المكتب (PyQt6 Admin App) بقاعدة البيانات المركزية على السيرفر.

---

## 📋 المتطلبات الأساسية
- سيرفر بنظام **Ubuntu 20.04 / 22.04 LTS** متاح عبر الإنترنت مع عنوان IP خارجي (Public IP).
- اسم نطاق (Domain Name) متموج وموجه لعرض IP السيرفر (اختياري ولكن يفضل للـ HTTPS).

---

## 📍 المرحلة 1: إعداد وتثبيت قاعدة البيانات المركزية (PostgreSQL)

### 1. تثبيت PostgreSQL على السيرفر:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install postgresql postgresql-contrib psycopg2-binary -y
```

### 2. إنشاء قاعدة البيانات والمستخدم:
```bash
sudo -i -u postgres psql
```
داخل شاشة SQL، قم بتنفيذ الأوامر التالية:
```sql
CREATE DATABASE hakbah_db;
CREATE USER hakbah_user WITH PASSWORD 'YourSecurePassword123';
GRANT ALL PRIVILEGES ON DATABASE hakbah_db TO hakbah_user;
ALTER DATABASE hakbah_db OWNER TO hakbah_user;
\q
```

### 3. السماح بالاتصال الخارجي في PostgreSQL:
قم بالتعديل على ملف `postgresql.conf`:
```bash
sudo nano /etc/postgresql/*/main/postgresql.conf
```
ابحث عن السطر `#listen_addresses = 'localhost'` وغيّره إلى:
```ini
listen_addresses = '*'
```

ثم قم بالتعديل على ملف `pg_hba.conf`:
```bash
sudo nano /etc/postgresql/*/main/pg_hba.conf
```
أضف السطر التالي في نهاية الملف للسماح باتصال الأجهزة الخارجية بالكلمة المشفرة:
```ini
host    all             all             0.0.0.0/0               md5
```

إعادة تشغيل خدمة PostgreSQL لتطبيق الإعدادات:
```bash
sudo systemctl restart postgresql
```

### 4. فتح بورت الاتصال بقاعدة البيانات (5432) في جدار الحماية:
```bash
sudo ufw allow 5432/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

---

## 📍 المرحلة 2: رفع وتجهيز الموقع على السيرفر (FastAPI Web App)

### 1. رفع أصل الكود للمسار التجميعي على السيرفر:
```bash
sudo mkdir -p /var/www/project-hakbah
sudo chown -R $USER:$USER /var/www/project-hakbah
cd /var/www/project-hakbah
# قم برفع ملفات المشروع إلى هنا عبر Git أو SFTP
```

### 2. إنشاء البيئة الافتراضية وتثبيت المكتبات:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install psycopg2-binary
```

### 3. إنشاء ملف البيئة `.env`:
```bash
# إعطاء صلاحيات المجلد للمستخدم الحالي أولاً لتفادي خطأ Permission denied
sudo chown -R $USER:$USER /var/www/project-hakbah

# إنشاء وتحرير ملف .env
sudo nano /var/www/project-hakbah/.env
```
ضع المحتوى التالي مع استبدال البيانات:
```env
DATABASE_URL=postgresql://hakbah_user:rageh62560@localhost:5432/hakbah_db
SECRET_KEY=331ac75e778e37d235d1c81465a07e9dec95f36c4166ca0706bd79ea395c8c9f
```

---

## 📍 المرحلة 3: تشغيل الموقع باستمرار عبر خدمة Systemd (24/7 Service)

إنشاء ملف خدمة لـ Systemd:
```bash
sudo nano /etc/systemd/system/hakbah-web.service
```

أضف المحتوى التالي داخل الملف:
```ini
[Unit]
Description=Hakbah Million FastAPI Web Server
After=network.target postgresql.service

[Service]
User=root
WorkingDirectory=/var/www/project-hakbah
ExecStart=/var/www/project-hakbah/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5
EnvironmentFile=/var/www/project-hakbah/.env

[Install]
WantedBy=multi-user.target
```

تفعيل وتشغيل الخدمة:
```bash
sudo systemctl daemon-reload
sudo systemctl enable hakbah-web
sudo systemctl start hakbah-web
```

للتحقق من حالة الخدمة وسجل الأخطاء:
```bash
sudo systemctl status hakbah-web
```

---

## 📍 المرحلة 4: إعداد Nginx وشهادة الأمان SSL (HTTPS)

### 1. تثبيت Nginx:
```bash
sudo apt install nginx certbot python3-certbot-nginx -y
```

### 2. إعداد موقع Nginx:
```bash
sudo nano /etc/nginx/sites-available/hakbah
```
أضف الإعدادات التالية (مع استبدال النطاق بـ hmillionair.com):
```nginx
server {
    server_name hmillionair.com www.hmillionair.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # إعدادات الـ WebSockets
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

تفعيل الموقع وإعادة تشغيل Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/hakbah /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. إصدار شهادة الأمان المجانية (Certbot SSL):
قم بتشغيل الأمر أدناه، وقم بإدخال بريدك الإلكتروني عند طلبه (أو إضافة البريد في الأمر مباشرة):
```bash
sudo certbot --nginx -d hmillionair.com -d www.hmillionair.com --m admin@hmillionair.com --agree-tos
```

---

## 📍 المرحلة 5: ترحيل البيانات الحالية (Data Migration)

لتصدير كافة المشتركين، الأقساط، الفئات، والمعلومات من قاعدة `hakbah.db` المحلية إلى قاعدة بيانات السيرفر PostgreSQL:

قم بتشغيل سكريبت الهجرة من جهازك أو من السيرفر:
```bash
python scripts/migrate_sqlite_to_postgres.py postgresql://hakbah_user:YourSecurePassword123@SERVER_IP:5432/hakbah_db
```
سيقوم السكريبت بإنشاء الهيكل ونقل السجلات وتحديث العدادات التلقائية بنجاح.

---

## 📍 المرحلة 6: ربط تطبيق سطح المكتب (Admin App) بالسيرفر

1. قم بفتح تطبيق سطح المكتب (`admin_app.py` / `HakbahMillionAdmin.exe`).
2. افتح شاشة **"إعدادات الشركة والمستخدمين"** ثم انتقل إلى تبويب **"الاتصال بالسيرفر"**.
3. اختر نوع قاعدة البيانات: **سيرفر خارجي (PostgreSQL مركزي)**.
4. أدخل البيانات التالية:
   - **عنوان السيرفر (IP / Host)**: IP السيرفر الخاص بك (مثلاً `123.45.67.89`).
   - **منفذ الاتصال**: `5432`
   - **اسم قاعدة البيانات**: `hakbah_db`
   - **اسم المستخدم**: `hakbah_user`
   - **كلمة المرور**: `YourSecurePassword123`
5. انقر على **"اختبار الاتصال بالسيرفر"** للتأكد من نجاح الوصول.
6. انقر على **"حفظ وإعادة الاتصال"**.

تهانينا! أصبح موقع الويب وتطبيق سطح المكتب يعملان بالتزامن المباشر واللحظي على قاعدة بيانات مركزية واحدة 24/7! 🎉

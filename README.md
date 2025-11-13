# AI STORYBOOK

ระบบจัดการชั้นเรียน (Django 5 + PostgreSQL + TailwindCSS) สำหรับนักเรียนและครู รองรับการสร้างห้องเรียน เข้าร่วม และอนุมัติผ่านแอดมิน



## Features
- สมัครสมาชิก (แยกบทบาท: นักเรียน / ครู / แอดมิน)
- ครูต้องรออนุมัติก่อนใช้งาน
- นักเรียนใช้รหัสเข้าร่วมชั้นเรียน
- แอดมินสามารถอนุมัติผู้ใช้งาน / ชั้นเรียน
- ระบบล็อกอิน/ล็อกเอาต์ / รีเซ็ตรหัสผ่าน
- แสดงชั้นเรียนทั้งหมดที่เกี่ยวข้องกับผู้ใช้


## Tech Stack
- Python 3.12
- Django 5.2
- PostgreSQL
- Tailwind CSS
- Django Allauth



## การติดตั้ง (Setup)

### 1. Clone โปรเจกต์
```
git clone https://github.com/Pratthana-da/DSSI-68.git 
```
```
cd DSSI-68
```



### 2. สร้าง Virtual Environment
```
py -3.12 -m venv .venv
```
```
python -m venv .venv
```

```
.venv\Scripts\activate
```   

### 3. ติดตั้ง dependencies
```
pip freeze > requirements.txt
```

```
pip install -r requirements.txt
```

### 4. ตั้งค่า Environment File
- สร้างไฟล์ .env แล้วใส่ค่าประมาณนี้:
- DEBUG=True
- SECRET_KEY=your-secret-key
- ALLOWED_HOSTS=127.0.0.1,localhost
- DATABASE_URL=postgres://USER:PASSWORD@localhost:5432/dssi68

### 5. รันคำสั่ง migrate
```
python manage.py makemigrations
```
```
python manage.py migrate
```

### 6. สร้าง superuser
```
python manage.py createsuperuser
```

### 7. รันโปรเจกต์
```
python manage.py runserver
```
```
uvicorn classroom_project.asgi:application --host 127.0.0.1 --port 8000 --reload
```


### ลงgit
### สร้าง Branch
```
git checkout -b feature-upload-pdf
```
```
git add .
```
```
git commit -m "เพิ่มหน้าอัปโหลด PDF"
```
```
git push origin feature-upload-pdf
```


### ดึงข้อมูล
```
git checkout main
```
```
git pull origin main
```

### รัน redis
```
redis-server.exe
```
### ประมวลผลได้ ทีละ 1 งาน เท่านั้น  pool=solo
```
celery -A classroom_project worker --loglevel=info --pool=solo
```
### ประมวลผลได้ ทีละหลายงาน concurrency=4 
```
celery -A classroom_project worker --loglevel=info --concurrency=4

celery -A classroom_project worker --concurrency=10 --loglevel=info

celery -A classroom_project worker --concurrency=5 --loglevel=info
# เปิดอีก terminal:
celery -A classroom_project worker --concurrency=5 --loglevel=info

```

### ยกเลิกการเปลี่ยนแปลงrequirements.txt
```
git restore requirements.txt
```
```
del .\security.log
```
### รัน uvicorn
```
uvicorn classroom_project.asgi:application --host 127.0.0.1 --port 8000
```


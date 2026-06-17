# AI STORYBOOK
# AI STORYBOOK

ระบบจัดการชั้นเรียน (Django + PostgreSQL + HTML + javascript + TailwindCSS + CSS) สำหรับนักเรียนและคุณครู รองรับการสร้างห้องเรียน เข้าร่วม และอนุมัติผ่านแอดมิน



## phases 1
- พัฒนาโปรเเกรมโครงสร้างระบบพื้นฐาน (Auth, Models, DB) 
- ระบบผู้ใช้ เช่น สมัคร, Login/Logout, Google Login
- สร้างชั้นเรียน 
- สร้างนิทานจากบทเรียน AI (Gemini) 
- สร้างฟอร์มแบบทดสอบหลังเรียน
- เข้าร่วมชั้นเรียน, ดูบทเรียน
- นักเรียนทำแบบทดสอบหลังเรียน
- สร้างฟอร์มแบบทดสอบหลังเรียน
- เพิ่มอีเมลและรหัสยืนยันตัวตนของคุณครู และอื่นฟังก์ชันหลักอื่น
## phases 2
- ระบบแจ้งเตือน, กดใจ, แชร์, ค้นหา , สถิติ
- ฟีเจอร์ Report, Dashboard ผู้ดูแล
- โปรไฟล์/ประวัติ
- Flipbook + PDF Download ,สิทธิ์ดาวน์โหลด
- และอื่นฟังก์ชันรองอื่นๆ


## Tech Stack
- Python 3.12
- Django 5.2
- PostgreSQL
- Tailwind CSS
- CSS
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
# Supabase
- SUPABASE_URL=https://klpksjclsuudum.supabase.co
- SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOc5fQ._-gDQsfevDAyBCGfdluILYDOP7S4gGKkd5T5wUKzwjM
- SUPABASE_BUCKET=AI_STORYBOOK

# Django settings
- SECRET_KEY = 'django-inskgbx275^ya!g@y15q83d6-029r'

- สร้าง api key ใน google ai studio
- GEMINI_API_KEY=AIzaSyA95P7oogiY

- GEMINI_TTS_VOICE=Leda
- GEMINI_TTS_LANG=th-TH
- ติดตั้งเเละดาวน์โหลดไว้ในเครื่อง
- FFMPEG_BIN=C:\ffmpeg\ffmpeg-8.0-full_build\bin\ffmpeg.exe
- FFPROBE_BIN=C:\ffmpeg\ffmpeg-8.0-full_build\bin\ffprobe.exe


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

### รัน redis
```
cd Redis-x64-5.0.14.1
```

```
.\redis-server.exe 
```

# เปิดอีก terminal
### ประมวลผลได้ ทีละ 1 งาน เท่านั้น  pool=solo
```
celery -A classroom_project worker --loglevel=info --pool=solo
```

```
celery -A classroom_project worker --loglevel=info --pool=threads --concurrency=4
```

### 7. รันโปรเจกต์
```
uvicorn classroom_project.asgi:application --host 127.0.0.1 --port 8000 --reload
```

### Push ลง git
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














 # คำแนะนำสำหรับ Copilot: โครงการ DSSI-68 (AI Storybook)

**โปรเจกต์**: ระบบจัดการชั้นเรียนที่แปลงบทเรียน PDF เป็นหนังสือนิทานพร้อมภาพและเสียง (AI)

## ภาพรวมสถาปัตยกรรม (สั้น)

 - Backend: Django 5.2 (+ DRF)
 - Real-time: Django Channels + Redis (WebSocket)
 - Task Queue: Celery + Redis
 - DB: PostgreSQL (User ยืดจาก `AbstractUser`)
 - เก็บไฟล์มีเดีย: Supabase Storage (ภาพ/เสียง)
 - บริการ AI: OpenAI (ภาพ/DALL·E, สรุปด้วย GPT) และ Google Gemini (TTS)
 - Frontend: Django templates + Tailwind CSS

## บทบาทผู้ใช้ (สำคัญ)
 - `student` — นักเรียน: เข้าร่วมห้องด้วยรหัส, ดู storybook, ทำ post-test, คอมเมนต์/กดชอบ
 - `teacher` — ครู: สร้าง/จัดการห้อง, อัปโหลด PDF → ระบบจะสร้าง storybook แบบอัตโนมัติ
 - `admin` — ผู้ดูแล: อนุมัติครู/ชั้นเรียน และจัดการผู้ใช้

ดูแบบจำลองผู้ใช้ที่สำคัญ: `classroom/models.py` (คลาส `User` มีฟิลด์ `user_type`, `is_approved`, `failed_login_attempts`)

## ข้อมูลการไหลที่สำคัญ (Storybook pipeline)

1) ครูอัปโหลด PDF → บันทึกเป็น `Storybook`
2) Celery task `process_storybook_async` ทำงาน:
   - ดึงข้อความจาก PDF (PyPDF2)
   - สรุปเป็นฉาก (GPT) พร้อม prompt สำหรับภาพ
   - สำหรับแต่ละฉาก: สร้างภาพ (DALL·E) → สร้างเสียง (Gemini TTS) → อัปโหลดไป Supabase → สร้าง `Scene` ใน DB
   - ขณะทำ จะส่งสถานะ/ฉากใหม่ผ่าน WebSocket ไปยัง group `storybook_{id}`
3) เมื่อเสร็จ: ติดธง `storybook.is_ready = True`

ไฟล์อ้างอิง: `classroom/tasks.py`, `classroom/consumers.py`, `classroom/utils.py`, `classroom/supabase_utils.py`

## ชื่อกลุ่ม WebSocket ที่ใช้บ่อย
 - ฉาก: `storybook_{storybook_id}`
 - คอมเมนต์: `comments_{storybook_id}`

Consumers ที่เกี่ยวข้อง: `SceneProgressConsumer`, `CommentConsumer`, `RatingConsumer` (ดู `classroom/routing.py`)

## โครงสร้างข้อมูลที่สำคัญ
 - `Classroom`: ใช้ UUID เป็น primary key, สร้าง `code` อัตโนมัติ (8 ตัวอักษร)
 - `Lesson` vs `Storybook`: `Lesson` คือไฟล์ต้นทาง, `Storybook` คือผลลัพธ์ที่ถูกประมวลผล
 - `PostTestQuestion` / `PostTestSubmission` / `PostTestAnswer` — แบบทดสอบหลังเรียน

## คำสั่งการพัฒนา (สั้นและใช้งานจริง)

การติดตั้งพื้นฐาน:
```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

ตั้งค่าไฟล์ `.env` (ตัวอย่างค่าที่สำคัญ):
```
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://USER:PASSWORD@localhost:5432/dssi68
OPENAI_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
SUPABASE_BUCKET=storybook
GEMINI_TTS_VOICE=Leda
FFMPEG_BIN=C:\ffmpeg\bin\ffmpeg.exe
```

รันแอป (เครื่องมือที่จำเป็น):
```powershell
# Redis (Channels + Celery)
redis-server.exe

# Django dev server (เบื้องต้น)
python manage.py runserver

# หรือใช้ ASGI/uvicorn เพื่อรองรับ WebSocket
uvicorn classroom_project.asgi:application --host 127.0.0.1 --port 8000 --reload

# Celery worker (ประมวลผล storybook)
celery -A classroom_project worker --loglevel=info --pool=solo
# หรือพร้อม concurrency
celery -A classroom_project worker --concurrency=4 --loglevel=info
```

## รูปแบบปฏิบัติที่ควรรู้ (Project-specific)
 - ฟอร์มแบบปลอดภัย: `classroom/forms.py` มี `SecureUserCreationForm` และ `SecureAuthenticationForm`
 - แยกข้อมูลผู้ใช้กับโปรไฟล์: `User` + `Profile` (1:1)
 - การลบคอมเมนต์เป็น soft-delete (`is_deleted`, `deleted_at`, `deleted_by`)
 - `StorybookRating` จำกัดให้ผู้ใช้ 1 คน ให้คะแนนได้ครั้งเดียว (unique_together)
 - การอัปโหลดไฟล์มีเดียหลักจะเก็บใน `media/` แต่ไฟล์ที่สร้างจาก AI (ภาพ/เสียง) จะอัปโหลดไป Supabase

## จุดเชื่อมต่อภายนอก (Integration)
 - OpenAI: สร้างภาพ / สรุปข้อความ
 - Google Gemini: TTS สำหรับภาษาไทย
 - Supabase Storage: เก็บภาพและไฟล์เสียง (ต้องสร้าง bucket ล่วงหน้า)

## ปัญหา/ข้อควรระวังที่ตรวจพบ
1. `User` ใช้ `email` เป็น `USERNAME_FIELD` — แบบ query และ form ต้องสอดคล้อง
2. โปรไฟล์รูปภาพอาจอยู่ได้ทั้งบน `Profile` และบน `User` — ให้เช็ก `profile` ก่อน
3. Redis ที่ใช้ไม่มีการตั้ง persistence ในโปรเจกต์นี้ — ข้อมูลคิวจะหายเมื่อ restart
4. Gmail SMTP ใน settings ต้องใช้ app-specific password

## แนวทางการเพิ่มฟีเจอร์โดยย่อ
1. แก้/เพิ่ม model (`classroom/models.py`) → `makemigrations` + `migrate`
2. เพิ่ม view / consumer (`classroom/views.py`, `classroom/consumers.py`) พร้อมการตรวจสิทธิ์บทบาท
3. เพิ่ม URL ใน `classroom/urls.py`
4. สร้าง template ใน `classroom/templates/` (Tailwind)
5. ถ้าเป็น real-time ให้เพิ่ม consumer ใน `classroom/routing.py` และใช้ group name ที่สอดคล้อง

---

ไฟล์นี้แปลและย่อเพื่อให้ AI agent (Copilot) อ่านแล้วเริ่มทำงานใน repo ได้เร็วขึ้น หากต้องการให้ขยายส่วนใดเป็นพิเศษ (เช่น ตัวอย่างโค้ดทดสอบ, mocking ของ OpenAI/Gemini, หรือคู่มือ deploy) กรุณาบอกผมได้เลย

**อัปเดตล่าสุด**: พฤศจิกายน 2025

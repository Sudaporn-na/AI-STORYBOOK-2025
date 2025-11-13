# ───────────────────────────────
# 🧩 SYSTEM / AUTH / OTP / COMMON
# ───────────────────────────────

from django import template
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from xhtml2pdf import pisa
import io, os, json, logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.template.loader import render_to_string
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.http import require_POST

from .forms import (
    SecureUserCreationForm,
    SecureAuthenticationForm,
    JoinClassroomForm,
    ProfileUpdateForm,
    UserUpdateForm,
    ReportForm,
)
from .models import (
    Scene,
    TeacherID,
    User,
    Classroom,
    EmailOTP,
    Storybook,
    Report,
    Lesson,
)
from .tasks import process_storybook_async
from .serializers import ClassroomSerializer
from .notify_utils import notify_user

logger = logging.getLogger("django.security")

# ==============================
# AUTH & ROLE SELECTION
# ==============================

DEFAULT_BACKEND = settings.AUTHENTICATION_BACKENDS[0]


def _get_safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return None


@csrf_protect
@never_cache
def auth_view(request):
    if request.user.is_authenticated:
        u = request.user
        if u.user_type == "teacher":
            return redirect("classroom_created")
        if u.user_type == "student":
            return redirect("courses_enroll")
        if u.user_type == "admin":
            return redirect("admin_lesson_dashboard")
        return redirect("select_role")

    login_form = SecureAuthenticationForm(request)
    register_form = SecureUserCreationForm()

    if request.method == "POST":
        action = request.POST.get("action")
        safe_next = _get_safe_next(request)

        # ===== LOGIN =====
        if action == "login":
            login_form = SecureAuthenticationForm(request, data=request.POST)
            register_form = SecureUserCreationForm()

            if login_form.is_valid():
                user = login_form.get_user()  # มาจาก authenticate() ในฟอร์มแล้ว
                backend = getattr(user, "backend", DEFAULT_BACKEND)
                login(request, user, backend=backend)
                logger.info("User %s logged in.", user.email)

                if safe_next:
                    return redirect(safe_next)

                if not user.user_type:
                    if user.is_superuser or user.is_staff:
                        user.user_type = "admin"
                        user.save(update_fields=["user_type"])
                        return redirect("admin_lesson_dashboard")
                    return redirect("select_role")

                if user.user_type == "teacher":
                    return redirect("classroom_created")
                if user.user_type == "student":
                    return redirect("courses_enroll")
                if user.user_type == "admin":
                    return redirect("admin_lesson_dashboard")
                return redirect("select_role")

            messages.error(request, "เข้าสู่ระบบไม่สำเร็จ โปรดตรวจสอบข้อมูลอีกครั้ง")

        # ===== REGISTER =====
        elif action == "register":
            register_form = SecureUserCreationForm(request.POST)
            login_form = SecureAuthenticationForm(request)

            if register_form.is_valid():
                user = register_form.save(commit=False)
                user.is_approved = True
                user.save()

                # เอารหัสผ่านจากฟอร์มมา authenticate เพื่อให้ได้ user ที่มี backend
                raw_password = register_form.cleaned_data.get("password1")
                authed = authenticate(
                    request,
                    username=user.email,   # คุณตั้ง USERNAME_FIELD = 'email'
                    password=raw_password,
                )
                if authed is not None:
                    backend = getattr(authed, "backend", DEFAULT_BACKEND)
                    login(request, authed, backend=backend)
                else:
                    # กันกรณีผิดปกติ (ไม่ควรเกิด) แต่ให้ล็อกอินได้ด้วย backend เริ่มต้น
                    login(request, user, backend=DEFAULT_BACKEND)

                logger.info("New user registered: %s", user.email)
                return redirect("select_role")

            messages.error(request, "สมัครสมาชิกไม่สำเร็จ โปรดตรวจสอบรายการที่มีข้อผิดพลาด")

        else:
            messages.error(request, "คำขอไม่ถูกต้อง")

    return render(
        request,
        "auth.html",
        {"login_form": login_form, "register_form": register_form},
    )


@login_required
def select_role_view(request):
    user = request.user

    # ถ้ามี user_type แล้วไม่ต้องเลือกซ้ำ
    if user.user_type == 'teacher':
        return redirect('classroom_created')
    elif user.user_type == 'student':
        return redirect('courses_enroll')
    elif user.user_type == 'admin': 
        return redirect('admin_lesson_dashboard')

    if request.method == 'POST':
        role = request.POST.get('role')

        if role == 'teacher':
            input_code = request.POST.get('teacher_code')
            match = TeacherID.objects.filter(email=user.email, teacher_code=input_code).first()

            if match:
                user.user_type = 'teacher'
                user.is_approved = True
                user.save()
                return redirect('classroom_created')
            else:
                messages.error(request, "รหัสประจำตัวครูไม่ถูกต้อง หรือยังไม่ได้ลงทะเบียน")

        elif role == 'student':
            user.user_type = 'student'
            user.is_approved = True
            user.save()
            return redirect('courses_enroll')

    return render(request, 'select_a_role.html')



# ==============================
# OTP RESET PASSWORD SYSTEM
# ==============================

User = get_user_model()


def _send_otp_email(to_email: str, first_name: str, code: str):
    subject = "รหัส OTP สำหรับรีเซ็ตรหัสผ่าน (หมดอายุภายใน 5 นาที)"
    body = (
        f"สวัสดี {first_name or ''}\n\n"
        f"รหัส OTP ของคุณคือ: {code}\n"
        f"**รหัสจะหมดอายุภายใน 5 นาที**\n\n"
        f"หากคุณไม่ได้ร้องขอ กรุณาเพิกเฉยอีเมลฉบับนี้"
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER)
    send_mail(subject, body, from_email, [to_email], fail_silently=False)


@csrf_protect
@never_cache
def request_otp_view(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        if not email:
            messages.error(request, "กรุณากรอกอีเมล")
            return redirect("request_otp")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "ไม่พบอีเมลนี้ในระบบ")
            return redirect("request_otp")

        otp_obj = EmailOTP.generate_otp(user=user, minutes=5)
        try:
            _send_otp_email(user.email, user.first_name, otp_obj.otp_code)
        except Exception as e:
            messages.error(request, f"ส่งอีเมลไม่สำเร็จ: {e}")
            return redirect("request_otp")

        request.session["otp_user_id"] = user.id
        request.session["otp_requested_at"] = timezone.now().isoformat()
        messages.success(request, "เราได้ส่งรหัส OTP ไปที่อีเมลของคุณแล้ว")
        return redirect("verify_otp")

    return render(request, "otp/request_otp.html")


@csrf_protect
@never_cache
def verify_otp_view(request):
    user_id = request.session.get("otp_user_id")
    if not user_id:
        messages.error(request, "เซสชันหมดอายุ กรุณาขอรหัสใหม่")
        return redirect("request_otp")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "ไม่พบผู้ใช้")
        return redirect("request_otp")

    if request.method == "POST":
        code = (request.POST.get("otp") or "").strip()
        if not code:
            messages.error(request, "กรุณากรอกรหัส OTP")
            return redirect("verify_otp")

        try:
            otp_obj = EmailOTP.objects.filter(user=user).latest("created_at")
        except EmailOTP.DoesNotExist:
            messages.error(request, "ไม่พบรหัส OTP กรุณาขอรหัสใหม่")
            return redirect("request_otp")

        if otp_obj.is_valid(code):
            request.session["otp_verified"] = True
            messages.success(request, "ยืนยัน OTP สำเร็จ โปรดตั้งรหัสผ่านใหม่")
            return redirect("reset_password_custom")
        else:
            messages.error(request, "รหัส OTP ไม่ถูกต้องหรือหมดอายุแล้ว")
            return redirect("verify_otp")

    return render(request, "otp/verify_otp.html")


@csrf_protect
@never_cache
def reset_password_custom(request):
    """
    หน้าตั้งรหัสผ่านใหม่ (เข้าถึงได้เมื่อ verify OTP แล้วเท่านั้น)
    """
    if not request.session.get("otp_verified"):
        messages.error(request, "ยังไม่ได้ยืนยัน OTP")
        return redirect("request_otp")

    user_id = request.session.get("otp_user_id")
    if not user_id:
        messages.error(request, "เซสชันหมดอายุ กรุณาขอรหัสใหม่")
        return redirect("request_otp")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "ไม่พบผู้ใช้")
        return redirect("request_otp")

    if request.method == "POST":
        new_password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""

        if len(new_password) < 8:
            messages.error(request, "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร")
            return redirect("reset_password_custom")

        if new_password != confirm_password:
            messages.error(request, "รหัสผ่านไม่ตรงกัน")
            return redirect("reset_password_custom")

        # ตั้งรหัสผ่านใหม่
        user.set_password(new_password)
        user.save()

        # ล้าง session ที่เกี่ยวข้องกับ OTP
        for key in ["otp_user_id", "otp_verified", "otp_requested_at"]:
            request.session.pop(key, None)

        messages.success(request, "เปลี่ยนรหัสผ่านเรียบร้อยแล้ว สามารถเข้าสู่ระบบได้")
        return redirect("auth_view")

    return render(request, "otp/reset_password_custom.html", {})

# ==============================
# OTHER COMMON SYSTEM VIEWS
# ==============================

def landing_page(request):
    return render(request, "landing.html")


@login_required
def logout_view(request):
    logger.info(f'User {request.user.email} logged out')
    logout(request)
    messages.success(request, 'ออกจากระบบแล้ว')
    return redirect('auth_view')


@login_required
def license_view(request):
    if request.user.user_type == "teacher":
        return render(request, "teacher/license.html")
    elif request.user.user_type == "student":
        return render(request, "student/license.html")
    else:
        return redirect("home")


@csrf_exempt
@login_required
def submit_report(request, storybook_id):
    if request.method == "POST":
        storybook = get_object_or_404(Storybook, pk=storybook_id)
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.storybook = storybook
            report.save()
            return JsonResponse({"status": "success"})
        else:
            return JsonResponse({"status": "error", "errors": form.errors})
    return JsonResponse({"status": "invalid method"})


def link_callback(uri, rel):
    """
    ให้ xhtml2pdf หาไฟล์ static และ media ถูกต้อง
    """
    if uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
    elif uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    else:
        return uri
    return path

from django.http import HttpResponseForbidden

def export_lesson_pdf(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)

    # ตรวจสอบสิทธิ์: ถ้าเป็นครูเจ้าของ หรือ นักเรียนที่ดูได้
    is_owner = storybook.user == request.user
    is_student_viewer = request.user.user_type == 'student'  # หรือจะตรวจสอบว่าลงทะเบียนชั้นเรียนนี้ก็ได้

    if not (is_owner or is_student_viewer):
        return HttpResponseForbidden("คุณไม่มีสิทธิ์ดาวน์โหลดบทเรียนนี้")

    scenes = storybook.scenes.order_by('scene_number')
    html = render_to_string('teacher/lesson_detail_for_pdf.html', {
        'storybook': storybook,
        'scenes': scenes,
    }, request=request)

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=buffer, link_callback=link_callback)
    if pisa_status.err:
        return HttpResponse('เกิดข้อผิดพลาดในการสร้าง PDF', status=500)

    if request.user.user_type == 'student' and not is_owner:
        try:
            teacher = storybook.user  # ครูเจ้าของบทเรียน
            notify_user(
                teacher,
                event_type="student_downloaded",
                verb="ดาวน์โหลด: นักเรียนดาวน์โหลดบทเรียนของคุณ",
                description=f"{request.user.get_full_name() or request.user.email} ดาวน์โหลด {storybook.title}",
                target_url=reverse("teacher_view_lesson_detail", args=[storybook.id]),
            )
        except Exception:
            # ไม่ให้การแจ้งเตือนทำให้การดาวน์โหลดล้ม
            pass

    buffer.seek(0)
    return HttpResponse(
        buffer,
        content_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="lesson_{storybook.id}.pdf"'
        }
    )


@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'ลบบัญชีของคุณเรียบร้อยแล้ว')
        return redirect('home')  # เปลี่ยนเป็นชื่อ URL หน้าแรกของคุณ
    return render(request, 'teacher/delete_account_confirm.html')



# ───────────────────────────────
# 👩‍🏫 TEACHER VIEWS
# ───────────────────────────────

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import os
import json
from django.db.models import Avg, Count
from django.db.models import Q


from .models import (
    Storybook,
    Lesson,
    Classroom,
    PostTestQuestion,
    PostTestSubmission,
    Comment,
    StorybookRating,
)
from .forms import (
    LessonUploadForm,
    ClassroomForm,
    ProfileUpdateForm,
    UserUpdateForm,
)
from .tasks import process_storybook_async
from .notify_utils import notify_user


# ==============================
# UPLOAD & VIEW LESSON
# ==============================


@login_required
def classroom_home(request, classroom_id):
    classroom = get_object_or_404(Classroom, id=classroom_id)

    # ตรวจสอบสิทธิ์เข้าถึง
    if request.user != classroom.teacher and request.user not in classroom.students.all():
        messages.error(request, 'คุณไม่มีสิทธิ์เข้าถึงชั้นเรียนนี้')
        return redirect('class_join_create')

    if request.user == classroom.teacher:
        # ครูเห็นทุก storybook ของตัวเองในคลาสนี้ทั้งที่อัปโหลดแล้ว/ยัง
        storybooks = classroom.storybooks.filter(user=request.user).order_by('-created_at')
        template_name = 'teacher/classroom_home.html'
    else:
        # นักเรียนเห็นเฉพาะที่ "พร้อมใช้งาน"
        storybooks = classroom.storybooks.filter(is_uploaded=True).order_by('-created_at')
        template_name = 'student/classroom_home.html'

    return render(request, template_name, {
        'classroom': classroom,
        'storybooks': storybooks
    })


@api_view(['GET'])
def classroom_list_api(request):
    user = request.user
    if user.user_type == 'teacher':
        classrooms = Classroom.objects.filter(teacher=user)
    elif user.user_type == 'student':
        classrooms = user.enrolled_classes.all()
    else:
        classrooms = Classroom.objects.none()
    
    serializer = ClassroomSerializer(classrooms, many=True)
    return Response(serializer.data)

@login_required
def create_classroom(request):
    if request.user.user_type != 'teacher':
        messages.error(request, 'เฉพาะครูเท่านั้น')
        return redirect('classroom_created')

    # ถ้ามี POST → สร้างห้องใหม่
    if request.method == 'POST':
        name = request.POST.get('subject_name','').strip()
        if name:
            Classroom.objects.create(
                name=name,
                teacher=request.user,
                is_approved=True
            )
            messages.success(request, f'สร้าง "{name}" สำเร็จ')
        return redirect('classroom_created')

    # GET: filter ด้วย q
    q = request.GET.get('q','').strip()
    qs = Classroom.objects.filter(teacher=request.user)
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, 'teacher/classroom_created.html', {
        'classrooms': qs,
        'q': q,
    })

@login_required
def upload_lesson_file(request, classroom_id):
    classroom = get_object_or_404(Classroom, id=classroom_id)

    if request.method == 'POST':
        form = LessonUploadForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.user = request.user
            lesson.classroom = classroom  # เชื่อมกับ classroom

            uploaded_file = request.FILES['file']
            filename = uploaded_file.name.rsplit('.', 1)[0]
            lesson.title = filename
            lesson.file = uploaded_file
            lesson.save()

            # สร้าง Storybook ที่เชื่อมกับ lesson
            storybook = Storybook.objects.create(
                user=request.user,
                classroom=classroom,  # 🔹 เพิ่ม relation ถ้ามี field นี้
                title=lesson.title,
                file=lesson.file
            )

            # เรียก Celery ทำงาน async
            process_storybook_async.delay(storybook.id)

            # notify_user(
            #     request.user,
            #     event_type="lesson_uploaded",
            #     verb="อัปโหลดสำเร็จ: คุณได้เพิ่มบทเรียนใหม่",
            #     description=storybook.title,
            #     target_url=reverse("teacher_view_lesson_detail", args=[storybook.id])
            # )

            # redirect ไปหน้า status หรือ classroom_home ก็ได้
            return redirect('detail_lesson', storybook_id=storybook.id)

        else:
            print("Form Errors:", form.errors)
    else:
        form = LessonUploadForm()

    return render(request, 'teacher/create_upload_image.html', {
        'form': form,
        'classroom': classroom
    })


# @login_required
# def view_uploaded_lesson(request, storybook_id):
#     # ถ้าเป็นหน้า teacher ให้ล็อคเจ้าของงานไว้ด้วย user=request.user
#     storybook = get_object_or_404(Storybook, id=storybook_id, user=request.user)

#     posttest_questions = PostTestQuestion.objects.filter(storybook=storybook)

#     # scenes เหมือนเดิม
#     scenes_qs = storybook.scenes.order_by('scene_number')

#     # คอมเมนต์ตั้งต้น (เอาไว้โชว์ทันทีตอนรีเฟรช)
#     comments = (
#         Comment.objects
#         .filter(storybook=storybook)
#         .select_related("author")        # ให้ดึงข้อมูลผู้เขียนมาพร้อมกัน
#         .order_by("-created_at")[:200]   # จำกัดจำนวนล่าสุด 200 รายการ
#     )
#     agg = storybook.ratings.aggregate(avg=Avg("value"), count=Count("id"))
#     user_rating = None
#     if request.user.is_authenticated:
#         user_rating = (StorybookRating.objects
#                        .filter(storybook=storybook, user=request.user)
#                        .values_list("value", flat=True).first())

#     context = {
#         'storybook': storybook,
#         'questions': posttest_questions,
#         'scenes': json.dumps(
#             list(scenes_qs.values('scene_number', 'text', 'image_url', 'audio_url')),
#             cls=DjangoJSONEncoder
#         ),
#         'comments': comments,            # ส่งให้ template ลูปแสดง
#         'comments_count': comments.count() if hasattr(comments, 'count') else len(comments),
#         "rating_avg": (agg["avg"] or 0),
#         "rating_count": agg["count"] or 0,
#         "user_rating": user_rating or 0,
#     }
#     return render(request, 'teacher/view_uploaded_lesson.html', context)



@login_required
def view_uploaded_lesson(request, storybook_id):
    # ตรวจสอบว่าผู้ใช้เป็นเจ้าของงาน
    storybook = get_object_or_404(Storybook, id=storybook_id, user=request.user)

    posttest_questions = PostTestQuestion.objects.filter(storybook=storybook)

    scenes_qs = storybook.scenes.order_by('scene_number')

    # 🌟 แก้ไข: ดึงเฉพาะ Top-level comments (parent_comment__isnull=True) 
    # และยังไม่ถูกลบ (is_deleted=False)
    comments = (
        Comment.objects
        .filter(storybook=storybook, parent_comment__isnull=True, is_deleted=False) 
        .select_related("author")
        # 🌟 เพิ่ม: ดึง replies และ author ของ replies มาพร้อมกัน
        .prefetch_related("replies", "replies__author") 
        .order_by("-created_at")[:200]
    )
    
    agg = storybook.ratings.aggregate(avg=Avg("value"), count=Count("id"))
    user_rating = None
    if request.user.is_authenticated:
        user_rating = (StorybookRating.objects
                       .filter(storybook=storybook, user=request.user)
                       .values_list("value", flat=True).first())

    context = {
        'storybook': storybook,
        'questions': posttest_questions,
        'scenes': json.dumps(
            list(scenes_qs.values('scene_number', 'text', 'image_url', 'audio_url')),
            cls=DjangoJSONEncoder
        ),
        'comments': comments, # ส่งเฉพาะ Top-level comments ที่ไม่ถูกลบ
        'comments_count': comments.count(),
        "rating_avg": (agg["avg"] or 0),
        "rating_count": agg["count"] or 0,
        "user_rating": user_rating or 0,
    }
    return render(request, 'teacher/view_uploaded_lesson.html', context)


@login_required
def teacher_view_storybook(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id, user=request.user)

    context = {
        'storybook': storybook,
    }
    return render(request, 'teacher/detail_lesson.html', context)


@login_required
@require_POST
def cancel_storybook(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id, user=request.user)

    classroom_id = storybook.classroom.id  # เก็บก่อนลบ
    storybook.delete()
    messages.warning(request, "ยกเลิกและลบนิทานเรียบร้อยแล้ว")

    return redirect('upload_lesson_file', classroom_id=classroom_id)


# ==============================
# CLASSROOM MANAGEMENT
# ==============================

@login_required
def class_create_teacher(request):
    if request.user.user_type != 'teacher':
        return redirect('dashboard')  # ป้องกัน student เข้ามา

    if request.method == 'POST':
        name = request.POST.get('name')
        cover_image = request.FILES.get('cover_image')
        description = request.POST.get('description')

        classroom = Classroom.objects.create(
            name=name,
            teacher=request.user,
            cover_image=cover_image,
            description=description
        )

        return redirect('classroom_home', classroom.id)

    # ถ้า GET
    classrooms = Classroom.objects.filter(teacher=request.user)
    return render(request, 'teacher/class_create.html', {
        'classrooms': classrooms
    })
    

@login_required
def delete_classroom(request, classroom_id):
    # ดึงเฉพาะ classroom ที่ user เป็น teacher ผู้สร้าง
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)
    if request.method == 'POST':
        classroom.delete()
        messages.success(request, f'ลบชั้นเรียน "{classroom.name}" เรียบร้อยแล้ว')
        return redirect('classroom_created')  # เปลี่ยนเป็นชื่อ URL ที่ต้องการกลับไป
    return redirect('classroom_home', classroom_id=classroom_id)


def edit_classroom(request, classroom_id):
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)

    if request.method == 'POST':
        form = ClassroomForm(request.POST, request.FILES, instance=classroom)
        if form.is_valid():
            form.save()
            messages.success(request, 'แก้ไขข้อมูลชั้นเรียนเรียบร้อยแล้ว')
            return redirect('classroom_created')
        # ถ้าไม่ valid form จะ fall through ไป render form พร้อม error
    else:
        form = ClassroomForm(instance=classroom)

    return render(request, 'teacher/edit_classroom.html', {
        'form': form,
        'classroom': classroom
    })



@login_required
def create_lesson_for_classroom(request, classroom_id):
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)

    if request.method == 'POST':
        form = LessonUploadForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.user = request.user
            lesson.classroom = classroom
            lesson.save()
            return redirect('lesson_success')  # หรือ redirect ไปยัง lesson list
    else:
        form = LessonUploadForm()

    return render(request, 'teacher/create_upload_image.html', {
        'form': form,
        'classroom': classroom
    })


# ==============================
# LESSON & POSTTEST MANAGEMENT
# ==============================


# ===== โมเดลที่อาจยังไม่มี ให้ try/except ไว้ก่อน เพื่อไม่ให้พัง =====
try:
    from .models import StorybookDownload
except Exception:  # noqa: BLE001
    StorybookDownload = None

try:
    from .models import StorybookShare
except Exception:  # noqa: BLE001
    StorybookShare = None


@login_required
def teacher_view_lesson_detail(request, storybook_id):
    """
    หน้าแดชบอร์ดสรุปบทเรียนของครู:
    - ภาพ/ชื่อเรื่อง/คำอธิบาย
    - การ์ด metric: ยอดดู, คะแนนเฉลี่ยโหวต, จำนวนโหวต, ความคิดเห็น, ดาวน์โหลด, แชร์, คะแนนเฉลี่ย post-test, จำนวนคนทำ
    - ตารางนักเรียน: คนล่าสุดที่ทำ + จำนวนครั้งที่ทำ
    """
    storybook = get_object_or_404(Storybook, id=storybook_id, user=request.user)

    # ------------------------------
    # 1) สถิติแบบทดสอบ (PostTest)
    # ------------------------------
    submissions = (
        PostTestSubmission.objects
        .filter(storybook=storybook)
        .select_related("user")
    )

    total_submissions = submissions.count()
    average_score = submissions.aggregate(avg=Avg("score"))["avg"] or 0
    total_views = StorybookAccess.objects.filter(storybook=storybook).count()

    # นับจำนวนครั้งที่แต่ละ user ทำ
    counts_map = {
        row["user_id"]: row["c"]
        for row in submissions.values("user_id").annotate(c=Count("id"))
    }

    # เอา submission ล่าสุดของแต่ละ user (PostgreSQL: distinct on)
    latest_submissions = (
        submissions.order_by("user_id", "-submitted_at").distinct("user_id")
    )

    students = [
        {
            "user": s.user,
            "submitted_at": s.submitted_at,
            "count": counts_map.get(s.user_id, 1),
        }
        for s in latest_submissions
    ]

    learners_count = (
    StorybookAccess.objects
    .filter(storybook=storybook)
    .values("user_id")
    .distinct()
    .count()
)


    # ------------------------------
    # 2) ความคิดเห็น / คอมเมนต์
    # ------------------------------
    feedback_count = Comment.objects.filter(
        storybook=storybook,
        is_deleted=False
    ).count()

    # ------------------------------
    # 3) เรตติ้ง (1–5)
    # ------------------------------
    rating_info = StorybookRating.objects.filter(storybook=storybook).aggregate(
        avg=Avg("value"),
        count=Count("id"),
    )
    rating_avg = round(rating_info["avg"] or 0, 1)
    rating_count = rating_info["count"] or 0

    # ------------------------------
    # 4) ดาวน์โหลด / แชร์ (ถ้ามีโมเดล)
    # ------------------------------
    if StorybookDownload:
        downloads_count = StorybookDownload.objects.filter(storybook=storybook).count()
    else:
        downloads_count = 0

    if StorybookShare:
        shares_count = StorybookShare.objects.filter(storybook=storybook).count()
    else:
        shares_count = 0

    # ------------------------------
    # 5) วิว (ถ้ามีฟิลด์ views ใน Storybook)
    # ------------------------------
    views_count = getattr(storybook, "views", 0)

    context = {
        "storybook": storybook,

        # metrics บนการ์ด
        "views_count": views_count,
        "rating_avg": rating_avg,
        "rating_count": rating_count,
        "feedback_count": feedback_count,
        "downloads_count": downloads_count,
        "shares_count": shares_count,
        "total_submissions": total_submissions,
        "average_score": average_score,
        "total_views": total_views,
        "learners_count": learners_count,
        # ตารางนักเรียนล่าสุด + จำนวนครั้งที่ทำ
        "students": students,
    }
    return render(request, "teacher/lesson_detail_stats.html", context)

@login_required
@require_POST
def final(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id, user=request.user)

    if request.method == 'POST':
        # บันทึก download permission
        permission = request.POST.get('download_permission', 'public')
        storybook.download_permission = permission

        # อัปเดตชื่อเรื่องใหม่ (กรณีมีแก้ไข)
        title = request.POST.get('title')
        if title:
            storybook.title = title

        # ตั้งค่า is_uploaded
        storybook.is_uploaded = True
        storybook.save()

        # URLs ปลายทาง
        teacher_url = reverse("teacher_view_lesson_detail", args=[storybook.id])
        student_url = reverse("student_display_lesson", args=[storybook.id])

    # แจ้งเตือน "หลังคอมมิตจริง" ทั้งครูและนักเรียน
        def _notify_all():
        # ครู
            notify_user(
                storybook.user,
                event_type="lesson_uploaded",
                verb="อัปโหลดเสร็จสิ้น: บทเรียนพร้อมแล้ว",
                description=storybook.title,
                target_url=teacher_url,
            )
        # นักเรียน (กันเผื่อครูไปอยู่ในรายชื่อนักเรียน)
            for student in storybook.classroom.students.exclude(id=storybook.user_id).distinct():
                notify_user(
                    student,
                    event_type="new_lesson",
                    verb="คุณครูได้เพิ่มบทเรียนใหม่",
                    description=storybook.title,
                    target_url=student_url,
                )

        transaction.on_commit(_notify_all)

        
        # ดึงข้อมูลคำถามแบบทดสอบ
        questions_json = request.POST.get('questions_json')
        if questions_json:
            try:
                questions_data = json.loads(questions_json)

                for q in questions_data:
                    PostTestQuestion.objects.create(
                        storybook=storybook,
                        question_text=q['question'],
                        choice_1=q['choices'][0],
                        choice_2=q['choices'][1],
                        choice_3=q['choices'][2],
                        choice_4=q['choices'][3],
                        correct_choice=q['correct'],
                        explanation=q.get('explanation', '') 
                    )
            except Exception as e:
                messages.error(request, f"เกิดข้อผิดพลาดในการบันทึกคำถาม: {str(e)}")

        messages.success(request, "อัปโหลดสำเร็จ!")
        return redirect('classroom_home', classroom_id=storybook.classroom.id)

    return redirect('detail_lesson', storybook_id=storybook.id)

register = template.Library()

@register.filter
def get_choice(question, index):
    return getattr(question, f'choice_{index}', '')



@login_required
def edit_posttest(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id, user=request.user)
    questions = PostTestQuestion.objects.filter(storybook=storybook).order_by('id')

    if request.method == 'POST':
        # --- Update existing questions ---
        for q in questions:
            if f'delete_{q.id}' in request.POST:
                q.delete()
                continue

            q.question_text = request.POST.get(f'question_{q.id}')
            q.choice_1 = request.POST.get(f'choice1_{q.id}')
            q.choice_2 = request.POST.get(f'choice2_{q.id}')
            q.choice_3 = request.POST.get(f'choice3_{q.id}')
            q.choice_4 = request.POST.get(f'choice4_{q.id}')
            q.correct_choice = int(request.POST.get(f'correct_{q.id}', 1))
            q.explanation = request.POST.get(f'explanation_{q.id}') or ''
            q.save()

        # --- Add new questions (support multiple) ---
        new_questions = request.POST.getlist('new_question[]')
        new_explanations = request.POST.getlist('new_explanation[]')
        new_choice1 = request.POST.getlist('new_choice1[]')
        new_choice2 = request.POST.getlist('new_choice2[]')
        new_choice3 = request.POST.getlist('new_choice3[]')
        new_choice4 = request.POST.getlist('new_choice4[]')

        for idx, question_text in enumerate(new_questions):
            if not question_text.strip():
                continue  # skip empty
            PostTestQuestion.objects.create(
                storybook=storybook,
                question_text=question_text.strip(),
                choice_1=new_choice1[idx].strip() if idx < len(new_choice1) else '',
                choice_2=new_choice2[idx].strip() if idx < len(new_choice2) else '',
                choice_3=new_choice3[idx].strip() if idx < len(new_choice3) else '',
                choice_4=new_choice4[idx].strip() if idx < len(new_choice4) else '',
                correct_choice=int(request.POST.get(f'new_correct_{idx}', 1)),
                explanation=new_explanations[idx].strip() if idx < len(new_explanations) else ''
            )

        messages.success(request, "บันทึกการเปลี่ยนแปลงเรียบร้อยแล้ว")
        return redirect('edit_posttest', storybook_id=storybook.id)

    return render(request, 'teacher/edit_posttest.html', {
        'storybook': storybook,
        'questions': questions,
    })



@login_required
def edit_lesson_detail(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id, user=request.user)

    # สร้าง Lesson ถ้ายังไม่มี
    if not storybook.lesson:
        lesson = Lesson.objects.create(
            user=storybook.user,
            classroom=storybook.classroom,
            title=storybook.title,
            file=storybook.file
        )
        storybook.lesson = lesson
        storybook.save()

    lesson = storybook.lesson

    if request.method == 'POST':
        title = request.POST.get('title')
        detail_lesson = request.POST.get('detail_lesson')
        additional_details = request.POST.get('Additional_lesson_details')
        download_permission = request.POST.get('download_permission')

        # อัปเดตข้อมูล
        if title:
            storybook.title = title
            lesson.title = title

        if detail_lesson is not None:
            storybook.detail_lesson = detail_lesson

        if additional_details is not None:
            storybook.Additional_lesson_details = additional_details

        if download_permission in ['public', 'private']:
            storybook.download_permission = download_permission

        storybook.save()
        lesson.save()

        messages.success(request, "อัปเดตข้อมูลบทเรียนเรียบร้อยแล้ว")
        return redirect('view_uploaded_lesson', storybook_id=storybook.id)

    classrooms = Classroom.objects.filter(teacher=request.user)
    return render(request, 'teacher/edit_lesson_detail.html', {
        'storybook': storybook,
        'lesson': lesson,
        'classrooms': classrooms
    })



@require_POST
@login_required
def delete_lesson(request):
    storybook_id = request.POST.get('storybook_id')
    try:
        storybook = Storybook.objects.get(id=storybook_id, user=request.user)
        storybook.delete()
        return JsonResponse({'success': True})
    except Storybook.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'บทเรียนไม่พบ'})


@login_required
def lesson_history_teacher(request):
    query = request.GET.get('q', '')

    # ดึงบทเรียนของครูคนนี้ที่อัปโหลดแล้ว
    storybooks_qs = Storybook.objects.filter(user=request.user, is_uploaded=True)

    # ถ้ามีคำค้นหา ให้ค้นหาทั้งชื่อบทเรียน และชื่อห้องเรียน
    if query:
        storybooks_qs = storybooks_qs.filter(
            Q(title__icontains=query) |
            Q(classroom__name__icontains=query)  # ← ตรงนี้!
        )

    storybooks_qs = storybooks_qs.order_by('-created_at')

    latest_storybooks = storybooks_qs[:3]
    storybooks = storybooks_qs[3:]

    return render(request, 'teacher/lesson_history.html', {
        'latest_storybooks': latest_storybooks,
        'storybooks': storybooks,
        'query': query,
    })


# ==============================
# TEACHER PROFILE
# ==============================

@login_required
def profile_settings_teacher(request):
    user = request.user
    profile = getattr(user, "profile", None)
    if profile is None:
        from .models import Profile
        profile, _ = Profile.objects.get_or_create(user=user)

    if request.method == "POST":
        uform = UserUpdateForm(request.POST, instance=user)
        pform = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if uform.is_valid() and pform.is_valid():
            uform.save()
            pform.save()
            messages.success(request, "อัปเดตโปรไฟล์เรียบร้อย")
            return redirect("profile_settings_teacher")
    else:
        uform = UserUpdateForm(instance=user)
        pform = ProfileUpdateForm(instance=profile)

    # ฟิลด์ที่ไม่ต้องแสดงใน Personal Info
    hidden_fields = [
        'profile_picture', 'bio', 'facebook', 'line',
        'teaching_subjects', 'class_code', 'classroom_link'
    ]

    return render(request, 'teacher/profile_settings_teacher.html', {
        "user_form": uform,
        "profile_form": pform,
        'hidden_fields': hidden_fields
    })


@login_required
def view_profile_teacher(request):
    user = request.user
    profile = getattr(user, "profile", None)
    hidden_fields = [
        'profile_picture', 'bio', 'facebook', 'line',
        'teaching_subjects', 'class_code', 'classroom_link',
        'username','email'

    ]
    return render(request, 'teacher/view_profile_teacher.html', {
        "user": user,
        "profile": profile,
        'hidden_fields': hidden_fields,
    })


@login_required
def teacher_profile(request):
    user = request.user
    profile = getattr(user, "profile", None)
    hidden_fields = [
        'profile_picture', 'bio', 'facebook', 'line',
        'teaching_subjects', 'class_code', 'classroom_link',
        'username','email'

    ],
    return render(request, 'student/view_profile_teacher.html', {
        "user": user,
        "profile": profile,
        'hidden_fields': hidden_fields,
    })


# ───────────────────────────────
# 🎓 STUDENT VIEWS
# ───────────────────────────────

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
import random
from django.db.models import OuterRef, Subquery, Prefetch, Max, F 


from .models import (
    Storybook,
    Classroom,
    StorybookAccess,
    PostTestQuestion,
    PostTestSubmission,
    PostTestAnswer,
    Comment,
    StorybookRating,
)
from .forms import (
    JoinClassroomForm,
    ProfileUpdateForm,
    UserUpdateForm,
)
from .notify_utils import notify_user


# ==============================
# CLASSROOM JOIN & VIEW LESSON
# ==============================
def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@login_required
def join_classroom(request):
    if request.user.user_type != 'student':
        messages.error(request, 'เฉพาะนักเรียนเท่านั้นที่สามารถเข้าร่วมชั้นเรียนได้')
        return redirect('courses_enroll')
    
    # ดึงคลาสที่เคยเข้าร่วม
    classrooms = request.user.enrolled_classes.filter(is_approved=True)

    if request.method == 'POST':
        form = JoinClassroomForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['classroom_code']
            try:
                classroom = Classroom.objects.get(code=code, is_approved=True)
                if request.user not in classroom.students.all():
                    classroom.students.add(request.user)

                    notify_user(
                        classroom.teacher,
                        event_type="student_joined",
                        verb="เข้าร่วมชั้นเรียน: นักเรียนเข้าสู่ห้องเรียนของคุณ",
                        description=f"{request.user.get_full_name() or request.user.email} เข้าร่วม {classroom.name}",
                        target_url=reverse("classroom_home", args=[classroom.id])  # classroom_id เป็น UUID → OK
                    )

                    messages.success(request, f'เข้าร่วมชั้นเรียน {classroom.name} สำเร็จ')
                    return redirect('courses_enroll')
                else:
                    messages.info(request, 'คุณเป็นสมาชิกของชั้นเรียนนี้อยู่แล้ว')
                    return redirect('courses_enroll')  # กลับมาหน้าเดิม
            except Classroom.DoesNotExist:
                messages.error(request, 'ไม่พบชั้นเรียนที่มีรหัสนี้')
    else:
        form = JoinClassroomForm()
    
    return render(request, 'student/courses_enroll.html', {
        'form': form,
        'classrooms': classrooms  # ส่งข้อมูลคลาสเข้าร่วมไปยัง template
    })

@login_required
def class_join_student(request):

    if request.user.user_type == 'student':
        classrooms = request.user.enrolled_classes.all()
    else:
        classrooms = Classroom.objects.none()

    return render(request, 'student/class_join.html', {
        'classrooms': classrooms
    })


@login_required
def student_view_storybook(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)

    # ตรวจสิทธิ์แบบเร็ว/ชัด: ผู้ใช้ต้องอยู่ใน classroom ของ storybook นี้
    # ถ้า related name ไม่ใช่ students ให้เปลี่ยนให้ตรงกับโมเดลของคุณ
    is_student = storybook.classroom.students.filter(id=request.user.id).exists()
    if not is_student:
        return HttpResponseForbidden("You do not have permission to view this storybook.")

    # กันนับถี่ ๆ: 1 user ต่อ storybook ต่อ 60 วินาที
    key = f"access:{storybook.id}:{request.user.id}"
    if not cache.get(key):
        StorybookAccess.objects.create(
            storybook=storybook,
            user=request.user,
            ip=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )
        cache.set(key, True, timeout=60)

    # ส่ง context เดียวพอ
    context = {
        "storybook": storybook,
    }
    return render(request, "student/detail_lesson_student.html", context)


# ==============================
# POST TEST & RESULT
# ==============================

@login_required
def take_post_test(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    # questions = list(PostTestQuestion.objects.filter(storybook=storybook))
    questions = list(storybook.questions.all())

    if request.method == 'POST':
        # สร้าง submission และบันทึกคำตอบ + คำนวณคะแนน
        submission = PostTestSubmission.objects.create(
            user=request.user,
            storybook=storybook,
            score=0
        )
        total_correct = 0
        for q in questions:
            sel = request.POST.get(f'question_{q.id}')
            if sel:
                sel = int(sel)
                PostTestAnswer.objects.create(
                    submission=submission,
                    question=q,
                    selected_choice=sel
                )
                if sel == q.correct_choice:
                    total_correct += 1
        submission.score = total_correct
        submission.save()

        notify_user(
            request.user,
            event_type="test_submitted",
            verb="ทำแบบทดสอบเสร็จ",
            description=f"คุณทำได้ {total_correct} คะแนน",
            target_url=reverse("quiz_result", args=[submission.id])  # path: post-test/<submission_id>/quiz-result/
        )

        # **Redirect ไปหน้า quiz_result**
        return redirect('quiz_result', submission.id)

    # GET: สุ่ม choices แล้ว render form
    randomized_questions = []
    for q in questions:
        choices = [(1, q.choice_1), (2, q.choice_2),
                   (3, q.choice_3), (4, q.choice_4)]
        random.shuffle(choices)
        randomized_questions.append({'question': q, 'choices': choices})

    return render(request, 'student/post_test_form.html', {
        'storybook': storybook,
        'randomized_questions': randomized_questions,
    })


@login_required
def quiz_result(request, submission_id):
    # แสดงคะแนน + ปุ่มไปดูรายละเอียด / กลับ
    submission = get_object_or_404(PostTestSubmission, id=submission_id, user=request.user)
    total_questions = submission.storybook.questions.count()
    return render(request, 'student/quiz_result.html', {
        'submission': submission,
        'total_questions': total_questions,
    })


@login_required
def post_test_result(request, submission_id):
    # รายละเอียดคำตอบแต่ละข้อ
    submission = get_object_or_404(PostTestSubmission, id=submission_id, user=request.user)
    answers = submission.answers.all()
    return render(request, 'student/post_test_result.html', {
        'submission': submission,
        'answers': answers,
    })


@login_required
def student_posttest_history(request, storybook_id, user_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    student = get_object_or_404(User, id=user_id)

    submissions = PostTestSubmission.objects.filter(
        user=student,
        storybook=storybook
    ).order_by('-submitted_at')

    return render(request, 'teacher/student_posttest_history.html', {
        'student': student,
        'submissions': submissions,
        'storybook': storybook
    })

# ==============================
# FAVORITES SYSTEM
# ==============================

@login_required
def student_favorites(request):
    storybooks = Storybook.objects.filter(favorites=request.user)
    return render(request, 'student/favorite_list.html', {'storybooks': storybooks})


@require_POST
@login_required
def toggle_favorite(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    if request.user in storybook.favorites.all():
        storybook.favorites.remove(request.user)
    else:
        storybook.favorites.add(request.user)
    return JsonResponse({'success': True})


def student_display_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    return render(request, 'teacher/student_display_lesson.html', {'lesson': lesson})



def detail_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    return render(request, 'teacher/detail_lesson.html', {'lesson': lesson})


def detail_lesson_all(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    scenes = Scene.objects.filter(storybook=storybook)
    return render(request, 'student/detail_lesson_all.html', {
        'storybook': storybook,
        'scenes': scenes
    })

def view_lesson_teacher(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    scenes = Scene.objects.filter(storybook=storybook)
    return render(request, 'teacher/view_lesson_teacher.html', {
        'storybook': storybook,
        'scenes': scenes
    })


# ==============================
# STUDENT LESSON HISTORY
# ==============================

@login_required
def student_lesson_history_view(request):
    user = request.user

    # Subquery เพื่อหา id ของ submission ล่าสุด (ล่าสุดต่อ storybook)
    latest_subquery = (
        PostTestSubmission.objects
        .filter(user=user, storybook=OuterRef('storybook'))
        .order_by('-submitted_at')
        .values('id')[:1]
    )

    # Filter เฉพาะ submission ที่ id ตรงกับ submission ล่าสุดต่อ storybook
    submissions = (
        PostTestSubmission.objects
        .filter(id__in=Subquery(latest_subquery))
        .select_related('storybook')
        .prefetch_related('storybook__scenes')
        .order_by('-submitted_at')
    )

    for sub in submissions:
        sub.total_questions = PostTestQuestion.objects.filter(storybook=sub.storybook).count()

    return render(request, 'student/lesson_history.html', {
        'submissions': submissions,
    })


@login_required
def student_lesson_detail_history(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    submissions = PostTestSubmission.objects.filter(user=request.user, storybook=storybook).order_by('-submitted_at')
    total_questions = PostTestQuestion.objects.filter(storybook=storybook).count()
    passing_score = total_questions * 0.6  # 60% ถือว่าผ่าน

    scenes = storybook.scenes.all()  # ✅ ดึงฉากทั้งหมดของ storybook
    cover_scene = scenes.first()     # ✅ เอาฉากแรกเป็นปก
    cover_image_url = cover_scene.image_url if cover_scene else None  # ป้องกันกรณีไม่มีฉากเลย

    return render(request, 'student/lesson_detail_with_score.html', {
        'storybook': storybook,
        'submissions': submissions,
        'total_questions': total_questions,
        'passing_score': passing_score,
        'cover_image_url': cover_image_url,
    })


# ==============================
# STUDENT PROFILE
# ==============================

@login_required
def profile_settings_student(request):
    user = request.user
    profile = getattr(user, "profile", None)
    if profile is None:
        from .models import Profile
        profile, _ = Profile.objects.get_or_create(user=user)

    if request.method == "POST":
        uform = UserUpdateForm(request.POST, instance=user)
        pform = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if uform.is_valid() and pform.is_valid():
            uform.save()
            pform.save()
            messages.success(request, "อัปเดตโปรไฟล์เรียบร้อย")
            return redirect("profile_settings_student")
    else:
        uform = UserUpdateForm(instance=user)
        pform = ProfileUpdateForm(instance=profile)

    # ฟิลด์ที่ไม่ต้องแสดงใน Personal Info
    hidden_fields = [
        'profile_picture', 'bio', 'facebook', 'line',
        'teaching_subjects', 'class_code', 'classroom_link'
    ]

    return render(request, 'student/profile_settings_student.html', {
        "user_form": uform,
        "profile_form": pform,
        'hidden_fields': hidden_fields
    })


@login_required
def view_profile_student(request):
    user = request.user
    profile = getattr(user, "profile", None)
    hidden_fields = [
        'profile_picture', 'bio', 'facebook', 'line',
        'teaching_subjects', 'class_code', 'classroom_link'
    ]
    return render(request, 'student/view_profile_student.html', {
        "user": user,
        "profile": profile,
        'hidden_fields': hidden_fields,
    })

# ───────────────────────────────
# 🛠 ADMIN VIEWS
# ───────────────────────────────

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Count
from django.urls import reverse

from .models import (
    User,
    TeacherID,
    Storybook,
    Lesson,
    Report,
)
from .forms import (
    ProfileUpdateForm,
)
from .notify_utils import notify_user



# ==============================
# USER MANAGEMENT
# ==============================

@login_required
def user_list_view(request):
    teachers = User.objects.filter(user_type='teacher')
    students = User.objects.filter(user_type='student')

    teacher_ids = TeacherID.objects.all()
    teacher_id_map = {t.email: t.teacher_code for t in teacher_ids}

    context = {
        "teachers": teachers,
        "students": students,
        "teacher_id_map": teacher_id_map,  # ส่งไป template
    }
    return render(request, 'admin/user_list.html', context)


def add_teacher_registry_view(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        teacher_code = request.POST.get("teacher_id")

        if not TeacherID.objects.filter(email=email, teacher_code=teacher_code).exists():
            TeacherID.objects.create(
                full_name=full_name,
                email=email,
                teacher_code=teacher_code
            )
            messages.success(request, "เพิ่มข้อมูลสำเร็จ")
            return redirect("add_teacher_registry")  # หรือชื่อ path ที่คุณใช้
        else:
            messages.error(request, "มีครูคนนี้อยู่แล้ว")

    # ดึงรายชื่อครูทั้งหมดมาส่งไปให้ template
    registered_teachers = TeacherID.objects.all()

    return render(request, "admin/add_teacher_registry.html", {
        "registered_teachers": registered_teachers
    })


def delete_teacher_view(request, teacher_id):
    if request.method == 'POST':
        teacher = get_object_or_404(TeacherID, id=teacher_id)
        teacher.delete()
        messages.success(request, "ลบคุณครูเรียบร้อยแล้ว")
    return redirect('add_teacher_registry')


@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def delete_user_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    return redirect('user_list')


# ==============================
# TEACHER LESSON MANAGEMENT
# ==============================

@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def teacher_lesson_list_view(request, teacher_id):
    teacher = get_object_or_404(User, id=teacher_id, user_type='teacher')
    lessons = Lesson.objects.filter(user=teacher)  # ถ้ามี foreignkey เป็น user

    context = {
        "teacher": teacher,
        "lessons": lessons,
    }
    return render(request, 'admin/teacher_lessons.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def delete_teacher_storybook_view(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    teacher_id = storybook.user.id
    storybook.delete()
    return redirect('teacher_storybooks_admin', teacher_id=teacher_id)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def delete_teacher_lesson_view(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    teacher_id = lesson.user.id
    lesson.delete()
    return redirect('teacher_storybooks_admin', teacher_id=teacher_id)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def admin_view_lesson_detail(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    scenes = storybook.scenes.order_by('scene_number')
    return render(request, 'admin/view_lesson_detail.html', {
        'storybook': storybook,
        'scenes': scenes,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def teacher_storybooks_admin_view(request, teacher_id):
    teacher = get_object_or_404(User, id=teacher_id)
    storybooks = Storybook.objects.filter(user=teacher).order_by('-created_at')
    return render(request, 'admin/teacher_storybooks.html', {
        'teacher': teacher,
        'storybooks': storybooks,
    })


# ==============================
# REPORT MANAGEMENT
# ==============================

@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def admin_reported_lessons_view(request):
    reports = Report.objects.select_related('storybook', 'user').order_by('-created_at')
    total_users = User.objects.exclude(user_type='admin').count()
    total_storybooks = Storybook.objects.count()
    storybooks = Storybook.objects.select_related('classroom', 'user').order_by('-created_at')

    return render(request, 'admin/dashboard_lesson_admin.html', {
        'reports': reports,
        'total_users': total_users,
        'total_storybooks': total_storybooks,
        'storybooks': storybooks,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def admin_report_detail_view(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    reports = Report.objects.filter(storybook=storybook).select_related('user')
    return render(request, 'admin/report_detail.html', {
        'storybook': storybook,
        'reports': reports,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or u.user_type == 'admin')
def delete_reported_storybook(request, storybook_id):
    storybook = get_object_or_404(Storybook, id=storybook_id)
    storybook.delete()
    messages.success(request, "ลบบทเรียนเรียบร้อยแล้ว")
    return redirect('admin_reported_lessons')


@login_required
def delete_storybook(request, storybook_id):
    if request.method == 'POST':
        storybook = get_object_or_404(Storybook, id=storybook_id)

        # ตรวจสอบสิทธิ์ (เฉพาะ admin หรือเจ้าของ)
        if request.user.user_type == 'admin' or request.user == storybook.user:
            storybook.delete()
            messages.success(request, "ลบบทเรียนเรียบร้อยแล้ว")
        else:
            messages.error(request, "คุณไม่มีสิทธิ์ลบบทเรียนนี้")

    return redirect('admin_lesson_dashboard')


# ==============================
# ADMIN PROFILE
# ==============================

@login_required
def profile_settings_admin(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('profile_settings_admin')  # redirect กลับมา path ของ student
    else:
        form = ProfileUpdateForm(instance=user)

    hidden_fields = [
        'profile_picture', 'bio', 'facebook', 'line',
        'teaching_subjects', 'class_code', 'classroom_link'
    ]

    return render(request, 'admin/profile_settings_admin.html', {
        'form': form,
        'hidden_fields': hidden_fields
    })


@login_required
def view_profile_admin(request):
    form = ProfileUpdateForm(instance=request.user)
    hidden_fields = [
        'profile_picture', 'bio', 'facebook', 'line',
        'teaching_subjects', 'class_code', 'classroom_link'
    ]
    return render(request, 'admin/view_profile_admin.html', {
        'form': form,
        'user': request.user,
        'hidden_fields': hidden_fields,
    })



# ───────────────────────────────
# 🔔 NOTIFICATION SYSTEM
# ───────────────────────────────

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

from .models import Notification


# ==============================
# VIEW NOTIFICATIONS
# ==============================

@login_required
def notifications_list(request):
    qs = Notification.objects.filter(user=request.user).order_by("-created_at")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page", 1))
    unread_count = qs.filter(is_read=False).count()
    template_name = "teacher/notification.html" if request.user.user_type == "teacher" else "student/notification.html"
    return render(request, template_name, {"notifications": page_obj, "unread_count": unread_count})


@login_required
@require_POST
def notifications_mark_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})


@login_required
def notifications_unread_count(request):
    c = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"count": c})

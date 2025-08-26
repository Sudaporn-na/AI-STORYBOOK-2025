# classroom/adapters.py

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.utils import get_username_max_length
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.urls import reverse
import string


class CustomAccountAdapter(DefaultAccountAdapter):
    def generate_unique_username(self, txts, regex=None):
        """
        สร้าง username จากชื่อหน้า email เช่น prarttnadavng
        ถ้าซ้ำ จะเติมเลขสุ่มท้าย เช่น prarttnadavng3021
        """
        base = "user"
        for txt in txts:
            if txt:
                base = slugify(txt.split("@")[0])  # ใช้ชื่อหน้า email
                break

        base = base[:get_username_max_length() - 4]  # จำกัดความยาว
        username = base

        from django.contrib.auth import get_user_model
        User = get_user_model()
        i = 1
        while User.objects.filter(username=username).exists():
            suffix = get_random_string(4, allowed_chars=string.digits)
            username = f"{base}{suffix}"
            i += 1
            if i > 10:  # ป้องกันลูปไม่จบ
                break
        return username


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_login_redirect_url(self, request):
        user = request.user
        if not user.user_type:
            return reverse('select_role')
        elif user.user_type == 'teacher':
            return reverse('classroom_created')
        elif user.user_type == 'student':
            return reverse('courses_enroll')
        return super().get_login_redirect_url(request)

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        # สร้าง username จาก email 
        if not user.username:
            user.username = user.email.split('@')[0]

        # หากเลือกบทบาทเป็นครู อนุมัติทันที
        if user.user_type == 'ครู':  # ใช้คำว่า 'ครู' ตามที่ใช้จริง
            user.is_approved = True

        user.save()
        return user


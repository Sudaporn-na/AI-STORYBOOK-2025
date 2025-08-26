# classroom/forms.py
from django import forms
from .models import Lesson, User, Report, Classroom
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.utils import timezone
import re
from django.contrib.auth import get_user_model

User = get_user_model()


class LessonUploadForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['file']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'age', 'gender', 'country',
                  'profile_picture', 'bio', 'facebook', 'line',
                  'teaching_subjects', 'class_code', 'classroom_link']

        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'w-full rounded-xl border px-4 py-3 text-sm resize-none'}),
            'facebook': forms.TextInput(attrs={'class': 'w-full mt-1 rounded-full border px-4 py-2'}),
            'line': forms.TextInput(attrs={'class': 'w-full mt-1 rounded-full border px-4 py-2'}),
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone', 'age', 'gender', 'country',
            'bio', 'profile_picture', 'facebook', 'line',
            'teaching_subjects', 'class_code', 'classroom_link'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full mt-1 rounded-full border px-4 py-2'
            })
        self.fields['bio'].widget.attrs.update({
            'class': 'w-full rounded-xl border px-4 py-3 text-sm resize-none',
            'rows': 4,
        })


class SecureUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("อีเมลนี้ถูกใช้งานแล้ว")
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError("ชื่อผู้ใช้ต้องมีเฉพาะตัวอักษร ตัวเลข และ underscore เท่านั้น")
        return username


class SecureAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'อีเมล'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่าน'}))
    
    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if email and password:
            try:
                user = User.objects.get(email=email)
                
                # Check if account is locked
                if user.account_locked_until and user.account_locked_until > timezone.now():
                    raise ValidationError("บัญชีถูกล็อก กรุณาลองใหม่ภายหลัง")
                
                # Check if user is approved
                # เฉพาะครูเท่านั้นที่ต้องรออนุมัติ
                if user.user_type == 'teacher' and not user.is_approved:
                    raise ValidationError("บัญชีครูยังไม่ได้รับการอนุมัติจากผู้ดูแลระบบ")

                self.user_cache = authenticate(self.request, username=email, password=password)
                if self.user_cache is None:
                    user.failed_login_attempts += 1
                    if user.failed_login_attempts >= 5:
                        user.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
                    user.save()
                    raise ValidationError("อีเมลหรือรหัสผ่านไม่ถูกต้อง")
                else:
                    user.failed_login_attempts = 0
                    user.account_locked_until = None
                    user.save()
            except User.DoesNotExist:
                raise ValidationError("อีเมลหรือรหัสผ่านไม่ถูกต้อง")
        
        return self.cleaned_data


class JoinClassroomForm(forms.Form):
    classroom_code = forms.CharField(
        max_length=10, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'รหัสชั้นเรียน'})
    )


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'detail']


class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['name', 'cover_image']

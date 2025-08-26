from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Classroom
from django.utils import timezone

@admin.action(description='อนุมัติผู้ใช้ที่เลือก')
def approve_selected_users(modeladmin, request, queryset):
    queryset.update(is_approved=True)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'user_type', 'is_approved', 'is_active', 'date_joined')
    list_filter = ('user_type', 'is_approved', 'is_active')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    actions = [approve_selected_users]
    ordering = ['-date_joined']

    fieldsets = UserAdmin.fieldsets + (
        ('ข้อมูลเพิ่มเติม', {
            'fields': ('user_type', 'is_approved', 'last_login_ip', 'failed_login_attempts'),
        }),
    )

@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'teacher', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('name', 'code', 'teacher__email')
    readonly_fields = ('code', 'created_at')

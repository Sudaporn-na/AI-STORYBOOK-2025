# classroom/context_processors.py
from .models import Classroom

def teacher_classrooms(request):
    if request.user.is_authenticated and request.user.user_type == 'teacher':
        classrooms = Classroom.objects.filter(teacher=request.user, is_approved=True)
        return {'classrooms': classrooms}
    return {}  # ผู้ใช้ยังไม่ login หรือไม่ใช่ครู

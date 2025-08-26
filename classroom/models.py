# models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model
import uuid
import secrets
import string

class User(AbstractUser):
    USER_TYPES = (
        ('student', 'นักเรียน'),
        ('teacher', 'ครู'),
        ('admin', 'ผู้ดูแลระบบ'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPES, blank=True, null=True)
    email = models.EmailField(unique=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    # models.py (User class)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    line = models.CharField(max_length=100, blank=True, null=True)
    teaching_subjects = models.CharField(max_length=200, blank=True, null=True)
    class_code = models.CharField(max_length=50, blank=True, null=True)
    classroom_link = models.URLField(blank=True, null=True)

    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

class Classroom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='ชื่อวิชา')
    code = models.CharField(max_length=10, unique=True, blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teaching_classes')
    students = models.ManyToManyField(User, related_name='enrolled_classes', blank=True)
    is_approved = models.BooleanField(default=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_classes')
    created_at = models.DateTimeField(auto_now_add=True)
    cover_image = models.ImageField(upload_to='classroom_covers/', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_unique_code()
        super().save(*args, **kwargs)
    
    def generate_unique_code(self):
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not Classroom.objects.filter(code=code).exists():
                return code



User = get_user_model()

class Lesson(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="lessons", null=True, blank=True) 
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='lessons/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    

from django.db import models
# models.py
class Storybook(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="storybooks", null=True, blank=True)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='lessons/')
    cover_image_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_ready = models.BooleanField(default=False)
    is_failed = models.BooleanField(default=False)
    is_uploaded = models.BooleanField(default=False)
    download_permission = models.CharField(max_length=10, choices=[('public', 'Public'), ('private', 'Private')], default='public')
    lesson = models.ForeignKey('Lesson', on_delete=models.CASCADE, related_name='storybook', null=True, blank=True)
    favorites = models.ManyToManyField(User, related_name='favorite_storybooks', blank=True)


class Scene(models.Model):
    storybook = models.ForeignKey(Storybook, related_name='scenes', on_delete=models.CASCADE)
    scene_number = models.PositiveIntegerField()
    text = models.TextField()
    image_prompt = models.TextField()
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    audio_url = models.URLField(max_length=1000, blank=True, null=True)  
    

class PostTestQuestion(models.Model):
    storybook = models.ForeignKey(Storybook, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()

    choice_1 = models.CharField(max_length=255)
    choice_2 = models.CharField(max_length=255)
    choice_3 = models.CharField(max_length=255)
    choice_4 = models.CharField(max_length=255)

    correct_choice = models.PositiveSmallIntegerField(choices=[(1, 'Choice 1'), (2, 'Choice 2'), (3, 'Choice 3'), (4, 'Choice 4')])
    explanation = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    
class PostTestSubmission(models.Model): 
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    storybook = models.ForeignKey(Storybook, on_delete=models.CASCADE)
    score = models.IntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.email} - {self.storybook.title} ({self.score})'


class PostTestAnswer(models.Model):
    submission = models.ForeignKey(PostTestSubmission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(PostTestQuestion, on_delete=models.CASCADE)
    selected_choice = models.PositiveSmallIntegerField()

    def is_correct(self):
        return self.selected_choice == self.question.correct_choice
    


class Report(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    storybook = models.ForeignKey('classroom.Storybook', on_delete=models.CASCADE)
    reason = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report by {self.user} on {self.storybook}"


    

class TeacherID(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_id', null=True, blank=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    teacher_code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.full_name} ({self.teacher_code})"
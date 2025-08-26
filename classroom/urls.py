# urls.py (classroom app)
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.auth_view, name='home'),
    path('auth/', views.auth_view, name='auth_view'),
    path('class-create/', views.class_create_teacher, name='class_create'),
    path('class-join/', views.class_join_student, name='class_join'),

    path('classroom-created/', views.create_classroom, name='classroom_created'),
    path('courses-enroll/', views.join_classroom, name='courses_enroll'),
    path('classroom/<uuid:classroom_id>/', views.classroom_home, name='classroom_home'),
    path('logout/', views.logout_view, name='logout'),
    path('courses-enrolled/', views.join_classroom, name='courses_enrolled'),
    path('api/classrooms/', views.classroom_list_api, name='api_classrooms'),
    path('accounts/auth/', views.auth_view, name='auth'),

    path('student/profile-settings-student/', views.profile_settings_student, name='profile_settings_student'),
    path('veiwe-profile-student/', views.view_profile_student, name='view_profile_student'),
    path('teacher/profile-settings-teacher/', views.profile_settings_teacher, name='profile_settings_teacher'),
    path('view-profile-teacher/', views.view_profile_teacher, name='view_profile_teacher'),
    path('school-admin/profile-settings-admin/', views.profile_settings_admin, name='profile_settings_admin'),
    path('view-profile-admin/', views.view_profile_admin, name='view_profile_admin'),

    path('classroom/<uuid:classroom_id>/create-upload/', views.upload_lesson_file, name='upload_lesson_file'),
    # path('classroom/<uuid:classroom_id>/create-upload-video/', views.upload_lesson_file_video, name='upload_lesson_file_video'),
    # path('notifications/', views.notifications_view, name='notifications'),
    path('admin/lesson/delete/<int:storybook_id>/', views.delete_storybook, name='delete_storybook'),
    path('school-admin/dashboard/', views.admin_reported_lessons_view, name='admin_lesson_dashboard'),

    path('school-admin/user-list/', views.user_list_view, name='user_list'),
    path("school-admin/add-teacher/", views.add_teacher_registry_view, name="add_teacher_registry"),
    path('school-admin/delete-teacher/<int:teacher_id>/', views.delete_teacher_view, name='delete_teacher'),
    path('school-admin/delete-user/<int:user_id>/', views.delete_user_view, name='delete_user'),
    path('school-admin/teacher/<int:teacher_id>/lessons/', views.teacher_lesson_list_view, name='teacher_lesson_list'),
    path('school-admin/teacher/lesson/<int:lesson_id>/delete/', views.delete_teacher_lesson_view, name='delete_teacher_lesson'),
    path('school-admin/reported-lessons/', views.admin_reported_lessons_view, name='admin_reported_lessons'),
    path('school-admin/report/<int:storybook_id>/', views.admin_report_detail_view, name='admin_report_detail'),
    path('school-admin/delete-storybook/<int:storybook_id>/', views.delete_reported_storybook, name='delete_reported_storybook'),
    path('school-admin/teacher/storybooks/<int:teacher_id>/', views.teacher_storybooks_admin_view, name='teacher_storybooks_admin'),
    path('school-admin/teacher/lesson/<int:storybook_id>/', views.admin_view_lesson_detail, name='admin_view_lesson_detail'),
    path('school-admin/teacher/storybook/delete/<int:storybook_id>/', views.delete_teacher_storybook_view, name='delete_teacher_storybook'),


    path('storybook/<int:storybook_id>/view/', views.teacher_view_storybook, name='detail_lesson'),
    path('storybook/<int:storybook_id>/view-uploaded/', views.view_uploaded_lesson, name='view_uploaded_lesson'),

    path('student/storybook/<int:storybook_id>/view/', views.student_view_storybook, name='student_display_lesson'),
    path('select-role/', views.select_role_view, name='select_role'),

    path('submit-report/<int:storybook_id>/', views.submit_report, name='submit_report'),

    path('final/<int:storybook_id>/', views.final, name='final'),

    path('lesson-history/', views.lesson_history_teacher, name='teacher_lesson_history'), 
    path('lesson/<int:storybook_id>/', views.teacher_view_lesson_detail, name='teacher_view_lesson_detail'),
    path('lesson/<int:storybook_id>/student/<int:user_id>/posttest-history/', views.student_posttest_history, name='student_posttest_history'),
    path('lesson/<int:storybook_id>/edit-posttest/', views.edit_posttest, name='edit_posttest'),
    path("lesson/<int:storybook_id>/edit-detail/", views.edit_lesson_detail, name="edit_lesson_detail"),
    path('lesson/ajax-delete/', views.delete_lesson, name='delete_lesson'),
    path("view-lesson-teacher/<int:storybook_id>/", views.view_lesson_teacher, name="view_lesson_teacher"),
    path('lesson/<int:storybook_id>/export-pdf/', views.export_lesson_pdf, name='lesson_detail_for_pdf'),
    path('account/delete/', views.delete_account, name='delete_account'),
    path('classroom/<uuid:classroom_id>/delete/', views.delete_classroom, name='delete_classroom'),
    path('license/', views.license_view, name='license'),
    path('lessons/create/<uuid:classroom_id>/', views.create_lesson_for_classroom, name='create_lesson_for_classroom'),
# classroom/urls.py
    path('storybook/<int:storybook_id>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('favorites/', views.student_favorites, name='student_favorites'),




    path('storybook/<int:storybook_id>/cancel/', views.cancel_storybook, name='cancel_storybook'),
    path('student/storybook/<int:storybook_id>/post-test/', views.take_post_test, name='take_post_test'),
    path('student/post-test/result/<int:submission_id>/', views.post_test_result, name='post_test_result'),
    path('post-test/<int:submission_id>/quiz-result/', views.quiz_result, name='quiz_result'),
    path("detail-lesson-all/<int:storybook_id>/", views.detail_lesson_all, name="detail_lesson_all"),


    path('student/lesson-history/', views.student_lesson_history_view, name='lesson_history'),
    path('student/lesson/<int:storybook_id>/detail/', views.student_lesson_detail_history, name='student_lesson_detail_history'),



    # Password reset URLs
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='password_reset_form.html'),name='password_reset'),
    path('password_reset_done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_reset_done.html'),name='password_reset_done'),
    path('password_reset_confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'),name='password_reset_confirm'),
    path('password_reset_complete', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),name='password_reset_complete'),   
] 

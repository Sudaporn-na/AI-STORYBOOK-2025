# urls.py (classroom app)
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    # ระบบทั่วไป
    path('', views.landing_page, name='landing'),
    path('auth/', views.auth_view, name='auth_view'),
    path('accounts/auth/', views.auth_view, name='auth'),
    path('logout/', views.logout_view, name='logout'),
    path('license/', views.license_view, name='license'),   # จะลบออกในอนาคตจ้าาาา
    path('select-role/', views.select_role_view, name='select_role'),
    path('submit-report/<int:storybook_id>/', views.submit_report, name='submit_report'),
    path('final/<int:storybook_id>/', views.final, name='final'),
    path('lesson/<int:storybook_id>/export-pdf/', views.export_lesson_pdf, name='lesson_detail_for_pdf'),
    path('account/delete/', views.delete_account, name='delete_account'),
    path('api/classrooms/', views.classroom_list_api, name='api_classrooms'),

    path("password/otp/request/", views.request_otp_view, name="request_otp"),
    path("password/otp/verify/", views.verify_otp_view, name="verify_otp"),
    path("password/otp/reset/", views.reset_password_custom, name="reset_password_custom"),


    # ครู (Teacher)
    path('class-create/', views.class_create_teacher, name='class_create'),
    path('classroom-created/', views.create_classroom, name='classroom_created'),
    path('classroom/<uuid:classroom_id>/', views.classroom_home, name='classroom_home'),
    path('classroom/<uuid:classroom_id>/create-upload/', views.upload_lesson_file, name='upload_lesson_file'),
    path('lessons/create/<uuid:classroom_id>/', views.create_lesson_for_classroom, name='create_lesson_for_classroom'),
    path('classroom/<uuid:classroom_id>/delete/', views.delete_classroom, name='delete_classroom'),
    path('classroom/<uuid:classroom_id>/edit/', views.edit_classroom, name='edit_classroom'),

    path('lesson-history/', views.lesson_history_teacher, name='teacher_lesson_history'),
    path('lesson/<int:storybook_id>/', views.teacher_view_lesson_detail, name='teacher_view_lesson_detail'),
    path('lesson/<int:storybook_id>/student/<int:user_id>/posttest-history/', views.student_posttest_history, name='student_posttest_history'),
    path('lesson/<int:storybook_id>/edit-posttest/', views.edit_posttest, name='edit_posttest'),
    path("lesson/<int:storybook_id>/edit-detail/", views.edit_lesson_detail, name="edit_lesson_detail"),
    path('lesson/ajax-delete/', views.delete_lesson, name='delete_lesson'),
    path("view-lesson-teacher/<int:storybook_id>/", views.view_lesson_teacher, name="view_lesson_teacher"),

    path('storybook/<int:storybook_id>/view/', views.teacher_view_storybook, name='detail_lesson'),
    path('storybook/<int:storybook_id>/view-uploaded/', views.view_uploaded_lesson, name='view_uploaded_lesson'),
    path('storybook/<int:storybook_id>/cancel/', views.cancel_storybook, name='cancel_storybook'),

    path('teacher/profile-settings-teacher/', views.profile_settings_teacher, name='profile_settings_teacher'),
    path('view-profile-teacher/', views.view_profile_teacher, name='view_profile_teacher'),
    path('teacher-view-profile/', views.teacher_profile, name='teacher_profile'),


    # นักเรียน (Student)
    path('class-join/', views.class_join_student, name='class_join'),
    path('courses-enroll/', views.join_classroom, name='courses_enroll'),
    path('classroom/<uuid:classroom_id>/leave/', views.leave_classroom, name='leave_classroom'),

    path('courses-enrolled/', views.join_classroom, name='courses_enrolled'),

    path('student/storybook/<int:storybook_id>/view/', views.student_view_storybook, name='student_display_lesson'),
    path('student/storybook/<int:storybook_id>/post-test/', views.take_post_test, name='take_post_test'),
    path('student/post-test/result/<int:submission_id>/', views.post_test_result, name='post_test_result'),
    path('post-test/<int:submission_id>/quiz-result/', views.quiz_result, name='quiz_result'),

    path('student/lesson-history/', views.student_lesson_history_view, name='lesson_history'),
    path('student/lesson/<int:storybook_id>/detail/', views.student_lesson_detail_history, name='student_lesson_detail_history'),

    path('student/profile-settings-student/', views.profile_settings_student, name='profile_settings_student'),
    path('veiwe-profile-student/', views.view_profile_student, name='view_profile_student'),

    path('storybook/<int:storybook_id>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('favorites/', views.student_favorites, name='student_favorites'),

    path("detail-lesson-all/<int:storybook_id>/", views.detail_lesson_all, name="detail_lesson_all"),

    path('reports/history/', views.reporting_history, name='reporting_history'),
    path('reports/delete/<int:report_id>/', views.delete_report, name='delete_report'),
    path('reports/edit/<int:report_id>/', views.edit_report, name='edit_report'),



    # แอดมิน (Admin)
    path('school-admin/dashboard/', views.admin_reported_lessons_view, name='admin_lesson_dashboard'),
    path('school-admin/user-list/', views.user_list_view, name='user_list'),
    path("school-admin/add-teacher/", views.add_teacher_registry_view, name="add_teacher_registry"),
    path('school-admin/delete-teacher/<int:teacher_id>/', views.delete_teacher_view, name='delete_teacher'),
    path('school-admin/delete-user/<int:user_id>/', views.delete_user_view, name='delete_user'),
    # path('school-admin/teachers/<int:pk>/edit/', views.edit_teacher, name='edit_teacher'),
    path('school-admin/teachers/<int:teacher_id>/edit/',views.edit_teacher,name='edit_teacher'),

    path('school-admin/teacher/<int:teacher_id>/lessons/', views.teacher_lesson_list_view, name='teacher_lesson_list'),
    path('school-admin/teacher/lesson/<int:lesson_id>/delete/', views.delete_teacher_lesson_view, name='delete_teacher_lesson'),
    path('school-admin/reported-lessons/', views.admin_reported_lessons_view, name='admin_reported_lessons'),
    path('school-admin/report/<int:storybook_id>/', views.admin_report_detail_view, name='admin_report_detail'),
    # path('school-admin/delete-storybook/<int:storybook_id>/', views.delete_reported_storybook, name='delete_reported_storybook'),
    path('school-admin/teacher/storybooks/<int:teacher_id>/', views.teacher_storybooks_admin_view, name='teacher_storybooks_admin'),
    path('school-admin/teacher/lesson/<int:storybook_id>/', views.admin_view_lesson_detail, name='admin_view_lesson_detail'),
    path('school-admin/teacher/storybook/delete/<int:storybook_id>/', views.delete_teacher_storybook_view, name='delete_teacher_storybook'),
    path('school-admin/delete-report/<int:report_id>/', views.delete_report, name='delete_report'),

    path('admin/lesson/delete/<int:storybook_id>/', views.delete_storybook, name='delete_storybook'),

    path('school-admin/profile-settings-admin/', views.profile_settings_admin, name='profile_settings_admin'),
    path('view-profile-admin/', views.view_profile_admin, name='view_profile_admin'),


    # การแจ้งเตือน (Notifications)
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/unread-count/', views.notifications_unread_count, name='notifications_unread_count'),
    path('notifications/mark-read/<int:pk>/', views.notifications_mark_read, name='notifications_mark_read'),
    path('notifications/mark-all-read/', views.notifications_mark_all_read, name='notifications_mark_all_read'),
    path('storybook/<uuid:storybook_id>/share/', views.share_storybook, name='share_storybook'),


]

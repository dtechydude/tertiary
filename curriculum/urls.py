from django.urls import path
from . import views


app_name = 'curriculum'

urlpatterns = [
    # --- Everyone ---
    path("calendar/", views.academic_calendar_view, name="academic-calendar"),
    path("faculties/", views.faculty_list_view, name="faculty-list"),
    path("faculties/<int:faculty_id>/", views.faculty_detail_view, name="faculty-detail"),
    path("departments/<int:department_id>/", views.department_detail_view, name="department-detail"),

    # --- Students ---
    path("my-programme/", views.my_programme_view, name="my-programme"),
    path("register/", views.course_registration_view, name="course-registration"),
    path("register/drop/<int:registration_id>/", views.drop_course_registration, name="drop-registration"),

    # --- Lecturers ---
    path("lecturer/courses/", views.lecturer_courses_view, name="lecturer-courses"),
    path(
        "lecturer/courses/<int:course_id>/<int:session_id>/<int:semester_id>/roster/",
        views.course_roster_view,
        name="course-roster",
    ),
    path("lecturer/department/", views.department_dashboard_view, name="department-dashboard"),

    # --- Admin / Registrar ---
    path("admin/registrations/pending/", views.pending_registrations_view, name="pending-registrations"),
    path(
        "admin/registrations/<int:registration_id>/validate/",
        views.validate_registration,
        name="validate-registration",
    ),
    path(
        "admin/registrations/<int:registration_id>/unvalidate/",
        views.unvalidate_registration,
        name="unvalidate-registration",
    ),
    path("admin/sessions/", views.session_admin_view, name="session-admin"),
    path("admin/sessions/<int:session_id>/set-current/", views.set_current_session, name="set-current-session"),
    path("admin/semesters/<int:semester_id>/set-current/", views.set_current_semester, name="set-current-semester"),

    #Course Frontend validations
    path("registrations/", views.course_registration_overview_view, name="registration_overview"),
    path("registrations/course/<int:course_id>/", views.course_registration_detail_view, name="registration_detail"),
    path("registrations/validate/", views.validate_course_registrations_view, name="validate_registrations"),
    path("registrations/revoke/", views.revoke_course_registrations_view, name="revoke_registrations"),

]

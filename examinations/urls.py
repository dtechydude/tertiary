from django.urls import path

from . import views

app_name = "examinations"

urlpatterns = [
    path("my-timetable/", views.student_exam_timetable_view, name="student_timetable"),
    path("timetable/", views.staff_exam_timetable_view, name="staff_timetable"),
]

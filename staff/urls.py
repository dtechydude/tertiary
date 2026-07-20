from django.urls import path
from staff import views as staff_views
from .views import(LecturerIDCardView, LecturerSelfDetailView, LecturerDetailView )


app_name ='staff'

urlpatterns = [

    path('lecturer_list/', staff_views.lecturers_list, name='lecturer-list'),
    path('my-courses/', staff_views.lecturer_my_courses, name='lecturer_my_courses'),
    path('course-assignments/', staff_views.admin_course_assignments, name='admin_course_assignments'),


    path('lecturer/<int:lecturer_id>/id-card/', LecturerIDCardView.as_view(), name='lecturer_id_card'), 
    
    # self view
    path('lecturer/me/', LecturerSelfDetailView.as_view(), name='lecturer_self_detail'),

    # admin view
    path('lecturer/<int:pk>/', LecturerDetailView.as_view(), name='lecturer_detail'),   

    path('profile/pdf/', staff_views.lecturer_self_profile_pdf, name='lecturer-self-profile-pdf'),
    path('<int:pk>/profile/pdf/', staff_views.lecturer_profile_pdf, name='lecturer-profile-pdf'),
        

]
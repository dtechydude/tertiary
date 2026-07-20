from django.urls import path
from pages import views as page_views
from . import views

app_name ='pages'

urlpatterns = [

     # Use Them interchangeably either the first or the second
     #the FIRST "requires separate file on kwikschools domain"
     # path('', page_views.schoolly_home, name='schoolly-home'), 
     # The SECOND "doesnt require separate file on kwikschools domain"   
     path('', page_views.landing_page, name='schoolly-home'), 

     path('dashboard/', page_views.dashboard, name="portal-home"),     
     path('help-center/', page_views.help_center, name='help-center'),
     path('support-info/', page_views.contact_support, name='support_info'),
     path('lock-screen/', page_views.lock_screen, name='lock-screen'),
     path('success-submission/', page_views.success_submission, name='success_submission'),
     path('birthday-list/', page_views.birthday_list, name='birthday_list'),
     path('students-phone-list/', page_views.student_phone_list_view, name='students_phone_list'),
     path('students-email-list/', page_views.student_email_list_view, name='students_email_list'),

     path('lecturers-phone-list/', page_views.lecturer_phone_list_view, name='lecturer_phone_list'),
     path('lecturers-email-list/', page_views.lecturer_email_list_view, name='lecturer_email_list'),

     path('video-guides/', page_views.video_guides_view, name='video-guides'),


]

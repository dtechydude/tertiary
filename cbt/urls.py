from django.urls import path
from cbt import views as cbt_views

app_name ='cbt'

urlpatterns = [

     path('', cbt_views.cbt_home, name='cbt-home'),
     path('order/', cbt_views.cbt_order, name='cbt-order'),
     path('lecturer/order/', cbt_views.cbt_lecturer_order, name='cbt_lecturer_order'),
     path('student/order/', cbt_views.student_cbt_home, name='cbt_student_home'),

#      path('request/submit/', cbt_views.submit_cbt_request, name='submit_request'),
#      # URL for the CBT exam request form
#      # path('request/', cbt_views.request_cbt_exam, name='request_exam'),
#      path('request/submit/', cbt_views.submit_cbt_request, name='submit_request'),

#      #For Real CBT

#      # 1. Existing Student Views
    path('', cbt_views.quiz_list_view, name='main-view'),
    
#     # 2. New Lecturer Views (Placed before <pk> to avoid routing conflicts)
#     path('cbt/', cbt_views.quiz_list_view, name='main-view'),
#     path('lecturer/add-quiz/', cbt_views.admin_add_quiz, name='lecturer-quiz-add'),

#     # Lecturer sees list of quizzes
    path('lecturer/add-question/', cbt_views.lecturer_add_question, name='lecturer-add-question'),

#     # Lecturer/admin clicks a specific quiz → add question form
#     path('lecturer/quiz/<int:quiz_id>/add-question/', cbt_views.lecturer_add_question, name='lecturer-add-question-quiz'),

#     path('<pk>/', cbt_views.quiz_detail_view, name='quiz-view'),
#     path('<pk>/data/', cbt_views.quiz_data_view, name='quiz-data-view'),
#     path('<pk>/save/', cbt_views.save_quiz_view, name='save-view'),

#     path('lecturer/quiz/<int:quiz_id>/questions/', cbt_views.lecturer_view_questions, name='lecturer-view-questions'),
    
    path('lecturerresults/', cbt_views.lecturer_results_view, name='lecturer-results-view'),
    path('results/export/csv/', cbt_views.export_results_csv, name='results-csv'),

#     path('lecturer/quiz/<int:quiz_id>/export/<str:export_type>/', cbt_views.export_questions,  name='export-questions'),


]

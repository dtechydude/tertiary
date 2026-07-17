from django.urls import path

from . import views

app_name = 'cbt'

urlpatterns = [
    # ---------------------------------------------------------------
    # Landing / guide pages
    # ---------------------------------------------------------------
    path('info/', views.cbt_home, name='cbt-home'),
    path('info/order/', views.cbt_order, name='cbt-order'),
    path('info/guide/', views.user_guide, name='user-guide'),
    path('info/request-exam/', views.request_cbt_exam, name='request-exam'),

    # ---------------------------------------------------------------
    # Student / candidate exam-taking flow
    # ---------------------------------------------------------------
    path('', views.quiz_list_view, name='main-view'),
    path('my-results/', views.student_results_view, name='student-results'),
    path('<int:pk>/', views.quiz_detail_view, name='quiz-view'),
    path('<int:pk>/data/', views.quiz_data_view, name='quiz-data-view'),
    path('<int:pk>/save/', views.save_quiz_view, name='save-view'),

    # ---------------------------------------------------------------
    # Admin / staff quiz setup
    # ---------------------------------------------------------------
    path('admin/add-quiz/', views.admin_add_quiz, name='admin-add-quiz'),

    # ---------------------------------------------------------------
    # Lecturer question-bank management
    # ---------------------------------------------------------------
    path('lecturer/questions/', views.lecturer_add_question, name='lecturer-add-question'),
    path(
        'lecturer/questions/<int:quiz_id>/',
        views.lecturer_add_question,
        name='lecturer-add-question-quiz',
    ),
    path('lecturer/questions/view/', views.lecturer_view_questions, name='lecturer-view-questions'),
    path(
        'lecturer/questions/view/<int:quiz_id>/',
        views.lecturer_view_questions,
        name='lecturer-view-questions-quiz',
    ),
    path(
        'lecturer/questions/<int:quiz_id>/export/<str:export_type>/',
        views.export_questions,
        name='export-questions',
    ),
    path(
        'lecturer/questions/<int:quiz_id>/bulk-upload/',
        views.lecturer_bulk_upload_questions,
        name='lecturer-bulk-upload-questions',
    ),

    # ---------------------------------------------------------------
    # Results
    # ---------------------------------------------------------------
    path('lecturer/results/', views.lecturer_results_view, name='lecturer-results-view'),
    path('results/export/csv/', views.export_results_csv, name='results-csv'),
]


from django.urls import path
from . import views
from django.urls import path
from results.views import ResultEntryView, StudentResultView
from results.views import TestView

from django.views.generic import TemplateView # For a simple placeholder home page


app_name ='results'

urlpatterns = [
    path('lecturer/submit-scores/', ResultEntryView.as_view(), name='lecturer_submit_scores'),
    path('student/results/', StudentResultView.as_view(), name='student_view_results'),

    #test DRF
    path('test/', TestView.as_view()),

]



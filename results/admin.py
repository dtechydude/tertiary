from doctest import Example
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
# from results.models import Examination, Score, MotorAbilityScore, MidTermScore, ResultPublication, SessionResultStatus
from curriculum.models import Semester
from .models import Examination
# add this because of the cbt
from django.utils.html import format_html
from django.urls import reverse




# @admin.register(Examination)
# class ExaminationAdmin(admin.ModelAdmin):
#     list_display = ['name', 'session', 'programme', 'semester',]

#     def view_quizzes_link(self, obj):
#         # This creates a URL to the Quiz Admin filtered by this specific Examination ID
#         # Replace 'cbt' with the actual name of your app if it differs
#         url = reverse('admin:cbt_quiz_changelist') + f'?examination__id__exact={obj.id}'
#         return format_html('<a class="button" style="background-color: #2c3e50; color: white; padding: 5px 10px;" href="{}">Manage CBT</a>', url)

#     view_quizzes_link.short_description = "CBT Control"


from tkinter import Widget
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Student


class StudentRegisterForm(forms.ModelForm):

    class Meta:
        model = Student
        fields = '__all__'
        
#TERTIARY LOGIC======================================

class StudentUpdateForm(forms.ModelForm):
    """
    Form for Admin Staff: 
    Focuses on Bio-data, Contact Info, and Medicals.
    Excludes sensitive academic and financial fields.
    """
    class Meta:
        model = Student
        fields = '__all__'
        exclude = (
            'user', 'matric_number', 'student_status', 
            'faculty', 'department', 'programme', 
            'date_admitted', 'fee_balance', 'level', 
            'current_semester', 'graduated'
        )
        widgets = {
            'DOB': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class SuperUserStudentUpdateForm(forms.ModelForm):
    """
    Form for Registrar/Superuser: 
    Has the power to change Levels, Departments, and Finances.
    """
    class Meta:
        model = Student
        fields = '__all__'
        exclude = ('user',) # Only exclude the User relationship
        widgets = {
            'DOB': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
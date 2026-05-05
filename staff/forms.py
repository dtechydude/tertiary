from tkinter import Widget
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Lecturer
from curriculum.models import Course, Level
# your_app_name/forms.py



# teacher
class LecturerRegisterForm(forms.ModelForm):

    class Meta:
        model = Lecturer
        fields = '__all__'
        

class LecturerUpdateForm(forms.ModelForm):

    class Meta:
        model = Lecturer
        fields = '__all__'
        # exclude = ('user',)


#staff
class StaffRegisterForm(forms.ModelForm):
    pass

    # class Meta:
    #     model = Staff
    #     fields = '__all__'
        

class StaffUpdateForm(forms.ModelForm):
    pass

    # class Meta:
    #     model = Staff
    #     fields = '__all__'
    #     # exclude = ('user',)




# Signup Form For Teachers 
class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email')
    
    # Custom validation to check if username is available
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if get_user_model().objects.filter(username=username).exists():
            raise ValidationError("This username is already taken. Please choose another.")
        return username

class LecturerForm(forms.ModelForm):
    # Add first_name and last_name fields to the form
    first_name = forms.CharField(max_length=150, required=True, label='First Name',
        widget=forms.TextInput(attrs={'placeholder': 'Enter First Name'}))
    last_name = forms.CharField(max_length=150, required=True, label='Last Name',
        widget=forms.TextInput(attrs={'placeholder': 'Enter Last Name'}))
    middle_name = forms.CharField(max_length=150, required=False, label='Middle Name',
        widget=forms.TextInput(attrs={'placeholder': 'Enter Middle Name'})),

    
    
    class Meta:
        model = Lecturer
        fields ='__all__'
        widgets = {
            'DOB': forms.DateInput(attrs={'type': 'date'}),
            'date_employed': forms.DateInput(attrs={'type': 'date'}),
            'guarantor_address': forms.Textarea(attrs={'rows': 2}),
            'next_of_kin_address': forms.Textarea(attrs={'rows': 2}),
        }
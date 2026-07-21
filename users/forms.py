from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile
from students.models import Student
from staff.models import Lecturer
# from staff.models import Teacher


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField()
    last_name = forms.CharField()
   

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']



class StudentEnrollmentForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [ 'phone', 'user_type' ]



class UserUpdateForm(forms.ModelForm):
    # email = forms.EmailField(required=False)
    # first_name = forms.CharField()
    # last_name = forms.CharField()

    class Meta:
        model = User
        fields = [ 'email', 'last_name', 'first_name', ]


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [ 'state_of_origin', 'bio', 'phone' ]
        # widgets = {
        #     'date_of_birth': forms.DateInput(
        #         format=('%d/%m/%Y'),
        #         attrs={'class': 'form-control', 
        #                'placeholder': 'Select a date',
        #                'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
        #               }),
        # }



class UserTwoUpdateForm(forms.ModelForm):
   
    class Meta:
        model = User
        fields = [ 'last_name', ]



class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        label='Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter Password'})
    )
    password2 = forms.CharField(
        label='Confirm Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repeat Password'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']
        widgets = {
            # In university systems, First Name is usually the Surname/Family Name
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Surname'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@university.edu'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_username', 'placeholder': 'Matric No. or Staff ID'}),
        }

    def clean_password2(self):
        cd = self.cleaned_data
        if cd.get('password') != cd.get('password2'):
            raise forms.ValidationError('Passwords do not match.')
        return cd.get('password2')


class StudentEnrollmentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'matric_number', 'middle_name', 'gender', 'DOB', 
            'department', 'programme', 'level', 'student_type',
            'date_admitted', 'blood_group', 'genotype', 'health_remark',
            'guardian_name', 'guardian_phone', 'relationship'
        ]
        widgets = {
            # We keep readonly, but the View will populate this from the username
            'matric_number': forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
            'DOB': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_admitted': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'health_remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Critical: Make matric_number not required in the form 
        # since we sync it from the User's username in the view.
        self.fields['matric_number'].required = False
        
        # 2. Add Bootstrap 'form-control' to all fields dynamically
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-control'})


# Lecturer Enrolment form
class LecturerEnrollmentForm(forms.ModelForm):
    class Meta:
        model = Lecturer
        fields = [
            'user', 'middle_name', 'department', 'position', 
            'gender', 'marital_status', 'DOB', 'date_employed', 
            'phone', 'address', 'highest_qualification', 'institution', 
            'year_obtained', 'professional_body', 'guarantor_name', 
            'guarantor_phone', 'next_of_kin_name', 'next_of_kin_phone'
        ]
        widgets = {
            'user': forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
            'DOB': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_employed': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].required = False
        # Dynamically add bootstrap classes to all fields
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-control'})


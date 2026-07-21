from django.shortcuts import render, redirect
import csv
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from users.forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, StudentEnrollmentForm, UserTwoUpdateForm, UserRegistrationForm
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from curriculum.models import SchoolIdentity
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from students.models import Student

from django.contrib.auth import views as auth_views
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, StudentEnrollmentForm, LecturerEnrollmentForm
from .models import Profile





# Enrollment of new student
def user_registration(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'New user account has been created!' )
            return redirect('/')
    else:
        form = UserRegisterForm()
        user = request.user
        if user.is_superuser or user.is_staff:
            return render(request, 'users/user_registration.html', {'form': form})
       

# TERTIARY ENROLMENT===================================================
#enrolment logic
@login_required
@transaction.atomic # Ensures database integrity
def student_enrollment(request):
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('pages:portal_home')

    if request.method == 'POST':
        u_form = UserRegistrationForm(request.POST)
        p_form = StudentEnrollmentForm(request.POST, request.FILES)

        if u_form.is_valid() and p_form.is_valid():
            user = u_form.save(commit=False)
            user.set_password(u_form.cleaned_data['password'])
            user.save()

            student = p_form.save(commit=False)
            student.user = user
            student.matric_number = user.username 
            student.save()

            messages.success(request, f'Student {student.matric_number} enrolled successfully!')
            # REDIRECT TO SUCCESS PAGE
            return redirect('success_page') 
        else:
            messages.error(request, "Enrollment failed. Please check the details in both tabs.")
    else:
        u_form = UserRegistrationForm()
        p_form = StudentEnrollmentForm()

    return render(request, 'users/student_enrollment.html', {
        'u_form': u_form,
        'p_form': p_form,
    })


@login_required
def enroll_success(request):
    return render(request, 'users/enroll_success.html')


@login_required
def lecturer_signup_success(request):
    return render(request, 'users/lecturer_signup_success.html')



def check_username(request):
    """
    Checks if a username is already taken.
    """
    if request.method == 'GET':
        username = request.GET.get('username', None)
        is_taken = User.objects.filter(username__iexact=username).exists()
        data = {
            'is_taken': is_taken
        }
        return JsonResponse(data)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

# TERTIARY LOGIC=========================
# Lecturer signup
def lecturer_enrollment(request):
    # 1. Authorization Check
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('pages:portal_home')

    if request.method == 'POST':
        u_form = UserRegistrationForm(request.POST)
        l_form = LecturerEnrollmentForm(request.POST, request.FILES)

        if u_form.is_valid() and l_form.is_valid():
            try:
                # Use atomic transaction so if one fails, both fail (no "ghost" users)
                with transaction.atomic():
                    # 2. Save User
                    user = u_form.save(commit=False)
                    user.set_password(u_form.cleaned_data['password'])
                    user.save()

                    # 3. Handle Profile (Ensure user_type is 'teacher')
                    # We use get_or_create in case a signal already created the profile
                    profile, created = Profile.objects.get_or_create(user=user)
                    profile.user_type = 'teacher'
                    profile.activate = True
                    profile.save()

                    # 4. Save Lecturer (Linked to User)
                    lecturer = l_form.save(commit=False)
                    lecturer.user = user
                    # Note: lecturer.staff_id is removed as it's now a property of the model
                    lecturer.save()

                messages.success(request, f'Lecturer {user.username} enrolled successfully!')
                return redirect('lecturer_success')
                
            except Exception as e:
                messages.error(request, f"A database error occurred: {e}")
        else:
            messages.error(request, "Enrollment failed. Please review the errors in each tab.")
    else:
        u_form = UserRegistrationForm()
        l_form = LecturerEnrollmentForm()

    return render(request, 'users/lecturer_enrollment.html', {
        'u_form': u_form,
        'l_form': l_form,
    })
 
    

# BASIC PROFILE UPDATE
@login_required
def profile_edit(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your profile has been updated successfully')
            return redirect('pages:success_submission')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
    }

    return render(request, 'users/profile.html', context)



# BASIC PROFILE UPDATE For Staff
@login_required
def employment_edit(request):
    if request.method == 'POST':
        u_form = UserTwoUpdateForm(request.POST, instance=request.user)
        p_form = TeacherEmploymentUpdateForm(request.POST, request.FILES, instance=request.user.teacher)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your profile has been updated successfully')
            return redirect('pages:success_submission')
    else:
        u_form = UserTwoUpdateForm(instance=request.user)
        p_form = TeacherEmploymentUpdateForm(instance=request.user.teacher)

    context = {
        'u_form': u_form,
        'p_form': p_form,
    }

    return render(request, 'users/employment_profile.html', context)


 # new user login logic   
def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Handle 'next' parameter for redirection after login
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('/dashboard/') # Redirect to a default page if no 'next'
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})


def user_logout(request):
    logout(request)
    # Redirect to a new URL. You have a few options:
    
    # Option 1: Redirect to the homepage
    return redirect('logout_success')  # Assumes you have a URL named 'home'


def logout_success(request):
    return render (request, 'users/logout.html')


@login_required
def users_home(request):
    return render(request, 'pages/portal_home.html')





# TERTIARY LOGIC =========================================
# all users
@login_required
def all_users(request):
    """
    A unified view to display all users, pulling identity from Profile,
    and role-specific data from Student or Lecturer models.
    """
    if not request.user.is_staff:
        return redirect('pages:portal_home')

    # Optimized Query: Joins Profile, Student, and Lecturer tables in one go
    all_users_list = User.objects.all().select_related(
        'profile', 
        'student', 
        'lecturer'
    ).order_by('last_name', 'first_name')

    # Handle CSV export request
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="schoolly_unified_users.csv"'

        writer = csv.writer(response)
        # Headers adjusted for multi-role portal
        writer.writerow([
            'ID/Matric', 'Surname', 'First Name', 'Email', 
            'Role', 'Phone', 'Department', 'Status'
        ])

        for u in all_users_list:
            prof = getattr(u, 'profile', None)
            
            # Determine Identifier (Matric for students, Username for others)
            if hasattr(u, 'student'):
                identifier = u.student.matric_number
                dept = u.student.department.name if u.student.department else "N/A"
            elif hasattr(u, 'lecturer'):
                identifier = u.username
                dept = u.lecturer.department.name if u.lecturer.department else "N/A"
            else:
                identifier = u.username
                dept = "N/A"

            writer.writerow([
                identifier,
                u.last_name,
                u.first_name,
                u.email,
                prof.get_user_type_display() if prof else "N/A",
                prof.phone if prof else "",
                dept,
                "Active" if (prof and prof.activate) else "Inactive"
            ])
        return response

    # Normal template rendering
    context = {
        'all_users': all_users_list,
        'total_count': all_users_list.count()
    }
    return render(request, 'users/all_registered_users.html', context)



class CustomLoginView(LoginView):
    template_name = 'users/login.html'

    def get_success_url(self):
               
        # If not a parent, use the default redirect URL
        return super().get_success_url()
    



class SafePasswordResetView(auth_views.PasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'registration/password_reset_email_text.txt'
    html_email_template_name = 'registration/password_reset_email.html'

    def get_extra_email_context(self):
        context = super().get_extra_email_context() or {}

        try:
            context['school_info'] = SchoolIdentity.objects.first()
        except (OperationalError, ProgrammingError):
            # Table does not exist yet (before migration)
            context['school_info'] = None

        return context



def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'New user account has been created!' )
            return redirect('pages:success_submission')
    else:
        form = UserRegisterForm()
        user = request.user
        if user.is_superuser or user.is_staff:
            return render(request, 'users/register.html', {'form': form})
        else:
            return render(request, 'pages/portal_home.html')       
    

from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from users.utils import generate_ref_code
from users.core.choices import NigerianState


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics', verbose_name='Profile Pic', blank=True, null=True,)
    phone = models.CharField(max_length=11, blank=True)
    state_of_origin = models.CharField(
            max_length=30,
            choices=NigerianState.choices,
            default=NigerianState.SELECT,
        )
    address = models.CharField(max_length=150, blank=True, null=True)
    bio = models.TextField(max_length=150, blank=True)

    select = 'select'
    teacher = 'teacher'
    student = 'student'
    admin = 'admin'   
    other_staff = 'other_staff'    
    parent = 'parent'  
       
 

    user_types = [
        (select, 'select'),
        (student, 'student'),
        (teacher, 'teacher'),
        (admin, 'admin'),
        (other_staff, 'other_staff'),        
        (parent, 'parent'),                   
             
    ]

    user_type = models.CharField(max_length=20, choices=user_types, default=select, blank=True, null=True)
    code = models.CharField(max_length=6, blank=True) 
    recommended_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,  related_name='ref_by' )
    activate = models.BooleanField(default=False, blank=True, verbose_name='active')   
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    
   
   
    class Meta:
        ordering = ['user']
        verbose_name = 'User Profiles'
        verbose_name_plural = 'User Profiles'

#this function returns the profile name in the admin panel profile table
    def __str__ (self):
        return f'username:- {self.user.username} - {self.user.last_name} - {self.user.first_name}'
    
    def get_recommended_profiles(self):
        qs = Profile.objects.all()
        # my_recs = [p for p in qs if p.recommended_by == self.user]
        my_recs = []
        for profile in qs:
            if profile.recommended_by == self.user:
                my_recs.append(profile)
        return my_recs


    
    def save(self, *args, **kwargs):
        if self.code =="":
            code = generate_ref_code()
            self.code = code
        super().save(*args, **kwargs)

   
    @property
    def image_url(self):
        if self.image:
            return self.image.url
        return '/static/pages/images/default.jpg'




class Dept(models.Model):
    id = models.CharField(primary_key='True', max_length=100)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'School Departments'
        verbose_name_plural = 'School Departments'

    
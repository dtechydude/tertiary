from django.db import models
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User
from django.urls import reverse
import os
from django.utils.html import strip_tags
from django_ckeditor_5.fields import CKEditor5Field
from embed_video.fields import EmbedVideoField
from django.core.exceptions import ValidationError
from djrichtextfield.models import RichTextField
# from portal.models import Dept
from django.db.models import Sum


from tinymce.models import HTMLField
# from portal.models import Dept
# from staff.models import Teacher


# Register School
class SchoolIdentity(models.Model):
    name = models.CharField(max_length=50)
    address_line_1 = models.CharField(max_length=60)
    address_line_2 = models.CharField(max_length=60, blank=True, null=True)
    phone1 = models.CharField(max_length=11)
    phone2 = models.CharField(max_length=11, blank=True, null=True)
    email = models.CharField(max_length=50)
    logo = models.ImageField(default='school_logo.jpg', upload_to='official_pics', help_text='must not exceed 180px by 180px in size')
    signature = models.ImageField(blank=True, null=True, upload_to='official_pics', help_text='must not exceed 180px by 180px in size')

    slug = models.SlugField(null=True, blank=True)

    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = 'School Identity'
        verbose_name_plural = "School Identity Settings"

    # code for ensuring that only single entry is made to this model
    def save(self, *args, **kwargs):
        # Check if any other instance of this model already exists
        if SchoolIdentity.objects.exists() and not self.pk:
            # If an instance exists and we are trying to create a *new* one (self.pk is None),
            # raise a ValidationError.
            raise ValidationError("There can be only one %s instance." % self._meta.verbose_name)
        return super().save(*args, **kwargs)
 
        

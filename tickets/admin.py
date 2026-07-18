# tickets/admin.py
#
# The K-12 version used django-import-export's ImportExportModelAdmin,
# which needs an extra package installed (django-import-export) and added
# to INSTALLED_APPS. Swapped for plain admin.ModelAdmin — zero extra
# dependencies, works out of the box on any host.

from django.contrib import admin
from .models import Ticket, Comment, TicketReadStatus


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'author', 'category', 'status', 'priority', 'is_broadcast', 'created_at']
    list_filter = ['status', 'priority', 'category', 'is_broadcast', 'created_at']
    search_fields = ['title', 'description', 'author__username', 'author__first_name', 'author__last_name']
    autocomplete_fields = ['author', 'assigned_to']
    date_hierarchy = 'created_at'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'ticket', 'author', 'is_admin_response', 'created_at']
    list_filter = ['is_admin_response', 'created_at']
    search_fields = ['text', 'author__username']


@admin.register(TicketReadStatus)
class TicketReadStatusAdmin(admin.ModelAdmin):
    list_display = ['user', 'ticket', 'read_at']
    search_fields = ['user__username', 'ticket__title']

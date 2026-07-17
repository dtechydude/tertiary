from django.contrib import admin

from .models import CourseMaterial, MaterialComment, MaterialReply, OnlineClassLink


class MaterialCommentInline(admin.TabularInline):
    model = MaterialComment
    extra = 0
    readonly_fields = ("author", "body", "created_at")
    can_delete = False


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "material_type", "week_number", "is_published", "uploaded_by", "created_at")
    list_filter = ("material_type", "is_published", "course__department", "course__programme")
    search_fields = ("title", "course__course_code", "course__title", "description")
    autocomplete_fields = ("course",)
    inlines = [MaterialCommentInline]


@admin.register(OnlineClassLink)
class OnlineClassLinkAdmin(admin.ModelAdmin):
    list_display = ("course", "platform", "label", "is_active", "created_by", "created_at")
    list_filter = ("platform", "is_active")
    search_fields = ("course__course_code", "course__title", "label")
    autocomplete_fields = ("course",)


@admin.register(MaterialComment)
class MaterialCommentAdmin(admin.ModelAdmin):
    list_display = ("material", "author", "created_at")
    search_fields = ("body", "author__username")


@admin.register(MaterialReply)
class MaterialReplyAdmin(admin.ModelAdmin):
    list_display = ("comment", "author", "created_at")
    search_fields = ("body", "author__username")

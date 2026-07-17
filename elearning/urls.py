from django.urls import path

from . import views

app_name = "elearning"

urlpatterns = [
    path("", views.my_elearning_dashboard, name="dashboard"),

    path("course/<int:course_id>/", views.course_material_list, name="material_list"),
    path("course/<int:course_id>/add/", views.course_material_create, name="material_create"),

    path("material/<int:pk>/", views.course_material_detail, name="material_detail"),
    path("material/<int:pk>/edit/", views.course_material_update, name="material_update"),
    path("material/<int:pk>/delete/", views.course_material_delete, name="material_delete"),

    path("course/<int:course_id>/class-link/add/", views.online_class_link_create, name="online_link_create"),
    path("class-link/<int:pk>/edit/", views.online_class_link_update, name="online_link_update"),
    path("class-link/<int:pk>/delete/", views.online_class_link_delete, name="online_link_delete"),
]

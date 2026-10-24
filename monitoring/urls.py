from django.urls import path

from . import views

app_name = "monitoring"
urlpatterns = [
    path("", views.index, name="index"),
    path("lists/add/", views.create_list, name="create_list"),
    path("lists/<int:pk>/delete/", views.delete_list, name="delete_list"),
    path("lists/<int:pk>/rules/add/", views.create_rule, name="create_rule"),
    path("rules/<int:pk>/delete/", views.delete_rule, name="delete_rule"),
    path("notifications/", views.inbox, name="inbox"),
    path("notifications/<int:pk>/read/", views.mark_read, name="mark_read"),
]

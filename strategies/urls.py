from django.urls import path

from . import views

app_name = "strategies"
urlpatterns = [
    path("", views.index, name="index"),
    path("create/", views.create, name="create"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
]

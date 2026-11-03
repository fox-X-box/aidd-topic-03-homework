from django.urls import include, path

from dashboard.views import (
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    ShareUpdateView,
    ObservationListView,
    ObservationCreateView,
    ObservationUpdateView,
    ObservationDeleteView,
)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("<int:pk>", ShareDetailView.as_view(), name="detail"),
    path("create", ShareCreateView.as_view(), name="create"),
    path("update/<int:pk>", ShareUpdateView.as_view(), name="update"),
    path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete"),
    path("observations/", ObservationListView.as_view(), name="observations"),
    path("observations/create", ObservationCreateView.as_view(), name="observation_create"),
    path("observations/update/<int:pk>", ObservationUpdateView.as_view(), name="observation_update"),
    path("observations/delete/<int:pk>", ObservationDeleteView.as_view(), name="observation_delete"),
    path("api/", include("dashboard.api.urls")),
]

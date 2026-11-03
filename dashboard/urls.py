from django.urls import include, path

from dashboard.views import (
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    ShareUpdateView,
    WatchlistCreateView,
    WatchlistDeleteView,
    WatchlistUpdateView,
    WatchlistView,
)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("watchlist/", WatchlistView.as_view(), name="watchlist"),
    path("watchlist/add/", WatchlistCreateView.as_view(), name="watchlist_add"),
    path(
        "watchlist/<int:pk>/edit/",
        WatchlistUpdateView.as_view(),
        name="watchlist_update",
    ),
    path(
        "watchlist/<int:pk>/delete/",
        WatchlistDeleteView.as_view(),
        name="watchlist_delete",
    ),
    path("<int:pk>", ShareDetailView.as_view(), name="detail"),
    path("create", ShareCreateView.as_view(), name="create"),
    path("update/<int:pk>", ShareUpdateView.as_view(), name="update"),
    path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete"),
    path("api/", include("dashboard.api.urls")),
]

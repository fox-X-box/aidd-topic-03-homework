from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("user/", include("user.urls")),
    # Keep old bookmarks working; canonical reverse() uses /user/.
    path("user", include(("user.urls", "user_legacy"), namespace="user_legacy")),
]

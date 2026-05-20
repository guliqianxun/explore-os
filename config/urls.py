from pathlib import Path

from django.contrib import admin
from django.http import FileResponse
from django.urls import include, path, re_path

from config.settings import FRONTEND_DIST

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
]

# Serve built frontend SPA at root
if FRONTEND_DIST:
    def spa_view(request):
        return FileResponse(open(FRONTEND_DIST / "index.html", "rb"))

    urlpatterns += [
        path("assets/<path:path>", lambda r, path: FileResponse(
            open(FRONTEND_DIST / "assets" / path, "rb")), name="frontend-assets"),
        re_path(r"^(?!api/|admin/).*", spa_view, name="frontend-spa"),
    ]

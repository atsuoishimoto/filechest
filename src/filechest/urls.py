from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings as django_settings
from . import views

app_name = "filechest"


urlpatterns = [
    # top page
    path("", views.home, name="home"),
    # Main UI
    path("<slug:volume_name>/", views.index, name="index"),
    path("<slug:volume_name>/browse/<path:subpath>/", views.index, name="browse"),
    path("<slug:volume_name>/preview/<path:filepath>", views.preview, name="preview"),
    # API - Read operations
    path("api/<slug:volume_name>/list/", views.api_list, name="api_list"),
    path(
        "api/<slug:volume_name>/list/<path:subpath>/",
        views.api_list,
        name="api_list_subpath",
    ),
    path("api/<slug:volume_name>/raw/<path:filepath>", views.api_raw, name="api_raw"),
    # API - Write operations
    path("api/<slug:volume_name>/mkdir/", views.api_mkdir, name="api_mkdir"),
    path("api/<slug:volume_name>/delete/", views.api_delete, name="api_delete"),
    path("api/<slug:volume_name>/rename/", views.api_rename, name="api_rename"),
    path("api/<slug:volume_name>/upload/", views.api_upload, name="api_upload"),
    path("api/<slug:volume_name>/copy/", views.api_copy, name="api_copy"),
    path("api/<slug:volume_name>/move/", views.api_move, name="api_move"),
]

if not getattr(django_settings, "FILECHEST_ADHOC_MODE", False):
    urlpatterns = [
        # login
        path(
            "login/",
            auth_views.LoginView.as_view(template_name="filechest/login.html"),
            name="login",
        ),
        path("logout/", views.logoutpage, name="logout"),
    ] + urlpatterns

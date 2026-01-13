"""
URL configuration for adhoc mode.

Does not include admin or authentication URLs.
"""

from django.urls import path, include

urlpatterns = [
    path("", include("filechest.urls")),
]

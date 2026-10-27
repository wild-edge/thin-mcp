from django.urls import path

from examples.django_ninja.api import api

urlpatterns = [path("mcp", api.urls)]

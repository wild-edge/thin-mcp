from django.urls import path

from examples.django_ninja.app import api

urlpatterns = [path("mcp", api.urls)]

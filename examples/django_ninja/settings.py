"""Minimal settings for running the unauthenticated local example."""

SECRET_KEY = "local-example-only"
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
ROOT_URLCONF = "examples.django_ninja.urls"
INSTALLED_APPS = ["examples.django_ninja.echoes"]
MIDDLEWARE: list[str] = []
USE_TZ = True
MCP_ECHO_ENABLED = True

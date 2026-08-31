import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        SECRET_KEY="thin-mcp-tests",
        USE_TZ=True,
    )
    django.setup()

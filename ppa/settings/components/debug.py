from ppa.settings import INSTALLED_APPS, MIDDLEWARE

# Configure internal IPs for access to view debug toolbar
INTERNAL_IPS = ["127.0.0.1", "localhost"]

# if django-debug-toolbar is installed, enable it
try:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE += ("debug_toolbar.middleware.DebugToolbarMiddleware",)
except ImportError:
    pass

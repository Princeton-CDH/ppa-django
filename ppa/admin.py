from django.contrib import admin


class LocalAdminSite(admin.AdminSite):
    """Custom admin site for PPA to override header & label."""

    site_header = "Princeton Prosody Archive administration"
    site_title = "Princeton Prosody Archive site admin"

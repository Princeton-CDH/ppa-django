from django.contrib.admin.apps import AdminConfig
from django.contrib.staticfiles.apps import StaticFilesConfig


class LocalAdminConfig(AdminConfig):
    default_site = "ppa.admin.LocalAdminSite"

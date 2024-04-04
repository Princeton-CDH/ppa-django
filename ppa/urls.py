"""PPA URL Configuration

"""
from django.conf import settings
from django.conf.urls.static import serve
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView, TemplateView
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps import Sitemap
from wagtail.contrib.sitemaps import views as sitemap_views
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from ppa.archive.sitemaps import ArchiveViewsSitemap, DigitizedWorkSitemap
from ppa.unapi.views import UnAPIView

# sitemap configuration for sections of the site
sitemaps = {
    "pages": Sitemap,  # wagtail content pages
    "archive": ArchiveViewsSitemap,
    "digitizedworks": DigitizedWorkSitemap,
}


urlpatterns = [
    re_path(
        r"^robots\.txt$",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    re_path(
        r"^favicon\.ico$",
        RedirectView.as_view(url="/static/favicon.ico", permanent=True),
    ),
    path("admin/", admin.site.urls),
    # pucas urls for CAS login
    path("accounts/", include("pucas.cas_urls")),
    path("archive/", include("ppa.archive.urls", namespace="archive")),
    # unapi service endpoint for Zotero
    path("unapi/", UnAPIView.as_view(), name="unapi"),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    # sitemaps
    re_path(
        r"^sitemap\.xml$",
        sitemap_views.index,
        {"sitemaps": sitemaps},
        name="sitemap-index",
    ),
    re_path(
        r"^sitemap-(?P<section>.+)\.xml$",
        sitemap_views.sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("", include(wagtail_urls)),
]

# serve media content for development
if settings.DEBUG:
    urlpatterns = [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ] + urlpatterns

    try:
        # include debug toolbar when available
        import debug_toolbar

        urlpatterns = [
            # include debug toolbar urls first to avoid getting caught by other urls
            re_path(r"^__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

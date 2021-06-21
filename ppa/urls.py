"""PPA URL Configuration

"""
from django.conf import settings
from django.conf.urls import url, include
from django.conf.urls.static import serve
from django.contrib import admin
from django.views.generic.base import TemplateView, RedirectView
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.core import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.contrib.sitemaps import views as sitemap_views, Sitemap

from ppa.unapi.views import UnAPIView
from ppa.archive.sitemaps import DigitizedWorkSitemap, ArchiveViewsSitemap


# sitemap configuration for sections of the site
sitemaps = {
    "pages": Sitemap,  # wagtail content pages
    "archive": ArchiveViewsSitemap,
    "digitizedworks": DigitizedWorkSitemap,
}


urlpatterns = [
    url(
        r"^robots\.txt$",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    url(
        r"^favicon\.ico$",
        RedirectView.as_view(url="/static/favicon.ico", permanent=True),
    ),
    url(r"^admin/", admin.site.urls),
    # grappelli URLS for admin related lookups & autocompletes
    url(r"^grappelli/", include("grappelli.urls")),
    # pucas urls for CAS login
    url(r"^accounts/", include("pucas.cas_urls")),
    url(r"^archive/", include("ppa.archive.urls", namespace="archive")),
    # unapi service endpoint for Zotero
    url(r"^unapi/$", UnAPIView.as_view(), name="unapi"),
    url(r"^cms/", include(wagtailadmin_urls)),
    url(r"^documents/", include(wagtaildocs_urls)),
    # sitemaps
    url(
        r"^sitemap\.xml$",
        sitemap_views.index,
        {"sitemaps": sitemaps},
        name="sitemap-index",
    ),
    url(
        r"^sitemap-(?P<section>.+)\.xml$",
        sitemap_views.sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    url(r"", include(wagtail_urls)),
]

# serve media content for development
if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        # include debug toolbar urls first to avoid getting caught by other urls
        url(r"^__debug__/", include(debug_toolbar.urls)),
        url(
            r"^media/(?P<path>.*)$",
            serve,
            {
                "document_root": settings.MEDIA_ROOT,
            },
        ),
    ] + urlpatterns

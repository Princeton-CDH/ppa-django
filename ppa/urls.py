"""ppa URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url, include
from django.conf.urls.static import serve
from django.contrib import admin
from django.views.generic.base import TemplateView
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.core import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.contrib.sitemaps import views as sitemap_views, Sitemap

from ppa.unapi.views import UnAPIView
from ppa.archive.sitemaps import DigitizedWorkSitemap, ArchiveViewsSitemap


# sitemap configuration for sections of the site
sitemaps = {
    'pages': Sitemap,  # wagtail content pages
    'archive': ArchiveViewsSitemap,
    'digitizedworks': DigitizedWorkSitemap,
}


urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    # grappelli URLS for admin related lookups & autocompletes
    url(r'^grappelli/', include('grappelli.urls')),
    # pucas urls for CAS login
    url(r'^accounts/', include('pucas.cas_urls')),
    url(r'^archive/', include('ppa.archive.urls', namespace='archive')),

    # unapi service endpoint for Zotero
    url(r'^unapi/$', UnAPIView.as_view(), name='unapi'),

    # for testing 500 errors
    url(r'^500/$', lambda _: 1/0),

    url(r'^cms/', include(wagtailadmin_urls)),
    url(r'^documents/', include(wagtaildocs_urls)),

    # sitemaps
    url(r'^sitemap\.xml$', sitemap_views.index, {'sitemaps': sitemaps},
        name='sitemap-index'),
    url(r'^sitemap-(?P<section>.+)\.xml$', sitemap_views.sitemap, {'sitemaps': sitemaps},
        name='django.contrib.sitemaps.views.sitemap'),

    url(r'', include(wagtail_urls)),
]

# serve media content for development
if settings.DEBUG:
    urlpatterns += [
        url(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]

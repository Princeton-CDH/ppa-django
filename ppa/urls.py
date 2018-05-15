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
from django.conf.urls import url, include
from django.contrib import admin
from django.views.generic.base import TemplateView
import mezzanine.urls

from ppa.unapi.views import UnAPIView
from ppa.archive.views import IndexView

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    # grappelli URLS for admin related lookups & autocompletes
    url(r'^grappelli/', include('grappelli.urls')),
    # pucas urls for CAS login
    url(r'^accounts/', include('pucas.cas_urls')),
    # placeholder for home page
    url(r'^$', IndexView.as_view(), name='home'),
    url(r'^archive/', include('ppa.archive.urls', namespace='archive')),

    # unapi service endpoint for Zotero
    url(r'^unapi/$', UnAPIView.as_view(), name='unapi'),

    # content pages managed by mezzanine
    url("^", include(mezzanine.urls))
]

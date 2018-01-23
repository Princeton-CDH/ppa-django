from django.conf.urls import url

from ppa.archive import views


urlpatterns = [
    url('^$', views.DigitizedWorkListView.as_view(), name='list'),
    url('^(?P<source_id>.+)/$', views.DigitizedWorkDetailView.as_view(), name='detail'),
]

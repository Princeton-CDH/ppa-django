from django.conf.urls import url

from ppa.archive import views


urlpatterns = [
    url('^$', views.ItemListView.as_view(), name='list'),
]

from django.conf.urls import url
from django.contrib.admin.views.decorators import staff_member_required

from ppa.archive import views


urlpatterns = [
    url('^collections/$', views.CollectionListView.as_view(),
        name='list-collections'),
    url(
        '^collections/add/$',
        staff_member_required(views.BulkAddCollectionView.as_view()),
        name='bulk-add'
    ),
    url('^csv/$', views.DigitizedWorkCSV.as_view(), name='csv'),
    url('^(?P<source_id>.+)/$',
        views.DigitizedWorkDetailView.as_view(), name='detail'),
    url('^$', views.DigitizedWorkListView.as_view(), name='list'),

]

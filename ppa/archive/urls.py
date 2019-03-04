from django.conf.urls import url
from django.contrib.admin.views.decorators import staff_member_required

from ppa.archive import views

app_name = 'ppa.archive'

urlpatterns = [
    url(
        r'^add-to-collection/$',
        staff_member_required(views.AddToCollection.as_view()),
        name='add-to-collection'
    ),
    url(r'^csv/$', views.DigitizedWorkCSV.as_view(), name='csv'),
    url(r'^opensearch-description/$',
        views.OpenSearchDescriptionView.as_view(), name='opensearch-description'),
    url(r'^record/(?P<record_id>\d+)/$',
        views.DigitizedWorkByRecordId.as_view(), name='record-id'),
    url(r'^(?P<source_id>.+)/$',
        views.DigitizedWorkDetailView.as_view(), name='detail'),
    url(r'^$', views.DigitizedWorkListView.as_view(), name='list'),

]

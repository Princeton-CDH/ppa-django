from django.conf.urls import url
from django.contrib.admin.views.decorators import staff_member_required

from ppa.archive import views


urlpatterns = [
    url('^$', views.DigitizedWorkListView.as_view(), name='list'),
    url(
        '^digitizedworks/autocomplete/$',
        staff_member_required(views.DigitizedWorkAutocomplete.as_view()),
        name='digitizedwork-autocomplete',
    ),
    url('^digitizedworks/(?P<source_id>.+)/$',
        views.DigitizedWorkDetailView.as_view(), name='detail'),
]

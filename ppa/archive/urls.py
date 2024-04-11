from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path, re_path

from ppa.archive import views

app_name = "ppa.archive"

urlpatterns = [
    path(
        "add-to-collection/",
        staff_member_required(views.AddToCollection.as_view()),
        name="add-to-collection",
    ),
    path(
        "opensearch-description/",
        views.OpenSearchDescriptionView.as_view(),
        name="opensearch-description",
    ),
    re_path(
        r"^record/(?P<record_id>\d+)/",
        views.DigitizedWorkByRecordId.as_view(),
        name="record-id",
    ),
    # excerpt original page may be numeric or alpha (e.g., roman numerals)
    re_path(
        r"^(?P<source_id>[^-]+)-p(?P<start_page>[\da-zA-Z]+)/",
        views.DigitizedWorkDetailView.as_view(),
        name="detail",
    ),
    re_path(
        r"^(?P<source_id>[^-]+)/",
        views.DigitizedWorkDetailView.as_view(),
        name="detail",
    ),
    path("", views.DigitizedWorkListView.as_view(), name="list"),
]

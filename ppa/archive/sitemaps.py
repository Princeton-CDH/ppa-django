from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from ppa.archive.models import DigitizedWork


class ArchiveViewsSitemap(Sitemap):
    """Sitemap for archive views that are not Wagtail pages but also
    not tied to models (currently archive search/browse page only)."""

    def items(self):
        # return list of view names
        return ["list"]

    def location(self, obj):
        # generate url based on archives url names
        return reverse("archive:{}".format(obj))

    def lastmod(self, obj):
        # both pages are modified based on changes to digitized works,
        # so return the most recent modification time of any of them
        most_recent_work = DigitizedWork.objects.order_by("-updated").first()
        if most_recent_work:
            return most_recent_work.updated


class DigitizedWorkSitemap(Sitemap):
    """Sitemap for :class:`~ppa.archive.models.DigitizedWork` detail
    pages. Does not include suppressed items."""

    def items(self):
        return DigitizedWork.objects.filter(status=DigitizedWork.PUBLIC)

    def lastmod(self, obj):
        return obj.updated

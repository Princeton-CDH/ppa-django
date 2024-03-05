from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from pairtree import storage_exceptions
from parasolr.django.signals import IndexableSignalHandler

from ppa.archive.models import DigitizedWork


class Command(BaseCommand):
    """Update database page counts for non-excerpted HathiTrust digitized items.
    By default, runs on all non-excerpted, public HathiTrust items.
    """

    help = __doc__

    #: normal verbosity level
    v_normal = 1
    #: verbosity level for the current run; defaults to 1 / normal
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            "source_ids", nargs="*", help="List of specific items to update (optional)"
        )

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.verbosity)
        source_ids = kwargs.get("source_ids", [])
        # page count does not affect solr indexing, so disconnect signal handler
        IndexableSignalHandler.disconnect()

        script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)

        # find all non-excerpted, non-suppressed hathi volumes
        hathi_vols = DigitizedWork.objects.filter(
            source=DigitizedWork.HATHI,
            item_type=DigitizedWork.FULL,
            status=DigitizedWork.PUBLIC,
        )
        # if source ids are specified, limit to those records only
        if source_ids:
            hathi_vols = hathi_vols.filter(source_id__in=source_ids)

        stats = {"updated": 0, "unchanged": 0, "missing_data": 0}

        for digwork in hathi_vols:
            try:
                # store the current page count
                old_page_count = digwork.page_count
                # recalculate page count from pairtree data
                # NOTE: this method automatically saves if page count changes
                digwork.page_count = digwork.count_pages()
                if digwork.has_changed("page_count"):
                    digwork.save()
                    stats["updated"] += 1
                    # create a log entry documenting page count change
                    LogEntry.objects.log_action(
                        user_id=script_user.pk,
                        content_type_id=digwork_contentype.pk,
                        object_id=digwork.pk,
                        object_repr=str(digwork),
                        change_message=f"Recalculated page count (was {old_page_count}, "
                        + f"now {digwork.page_count})",
                        action_flag=CHANGE,
                    )

                else:
                    stats["unchanged"] += 1

            except storage_exceptions.ObjectNotFoundException:
                if self.verbosity >= self.v_normal:
                    self.stderr.write(
                        self.style.WARNING(f"Pairtree data for {digwork} not found")
                    )
                stats["missing_data"] += 1

        # report a summary of what was done
        if self.verbosity >= self.v_normal:
            self.stdout.write(
                f"Volumes with updated page count: {stats['updated']:,}"
                + f"\n\tPage count unchanged: {stats['unchanged']:,}"
                + f"\n\tMissing pairtree data: {stats['missing_data']:,}"
            )

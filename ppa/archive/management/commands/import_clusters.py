import csv
import logging
from collections import Counter

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize

from ppa.archive.models import Cluster, DigitizedWork, Page

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Import cluster information for records already in the system"""

    help = __doc__

    stats = None
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    required_fields = [
        "Source ID",
        "UNIQUE ID",
        "Pages (digital)",
    ]

    # cached local copy of clusters
    _clusters = {}

    def add_arguments(self, parser):
        parser.add_argument(
            "csv",
            help="CSV file with records and cluster ids for import",
        )

    def handle(self, *args, **kwargs):
        data = self.load_csv(kwargs["csv"])

        self.verbosity = kwargs.get("verbosity", self.v_normal)
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)
        self.cluster_contentype = ContentType.objects.get_for_model(Cluster)

        self.stats = Counter()

        for row in data:
            # if no cluster id is set, nothing to do
            if not row["UNIQUE ID"]:
                continue

            # - find the correct record
            # use an unsaved digitized work to parse the page range for search filter
            dw_pages = DigitizedWork(
                pages_digital=row["Pages (digital)"].replace(";", ",")
            )
            try:
                digwork = DigitizedWork.objects.get(
                    source_id=row["Source ID"], pages_digital=dw_pages.pages_digital
                )
                if self.verbosity > self.v_normal:
                    print(digwork)
            except DigitizedWork.DoesNotExist:
                # count missing and report
                self.stats["not_found"] += 1
                self.stdout.write(
                    self.style.WARNING(
                        "%s%s not found"
                        % (
                            row["Source ID"],
                            " (%s)" % dw_pages.pages_digital
                            if dw_pages.pages_digital
                            else "",
                        )
                    )
                )
                # skip to next row
                continue

            # associate with the cluster if set
            previous_cluster = digwork.cluster
            digwork.cluster = self.get_cluster(row["UNIQUE ID"])
            # save if changed
            if digwork.cluster != previous_cluster:
                self.stats["updated"] += 1
                digwork.save()

                # create a log entry
                LogEntry.objects.log_action(
                    user_id=self.script_user.pk,
                    content_type_id=self.digwork_contentype.pk,
                    object_id=digwork.pk,
                    object_repr=str(digwork),
                    change_message="Set cluster membership via CSV",
                    action_flag=CHANGE,
                )

            # reindex pages to ensure they have the new group id
            # TODO: maybe optional?
            # FIXME: index pages after using optimized script!
            digwork.index_items(Page.page_index_data(digwork))

        # summarize what was done
        summary = (
            "\nUpdated {:,d} record{}; {:,d} not found." + "\nCreated {:,d} cluster{}."
        )
        summary = summary.format(
            self.stats["updated"],
            pluralize(self.stats["updated"]),
            self.stats["not_found"],
            self.stats["clusters_created"],
            pluralize(self.stats["clusters_created"]),
        )
        self.stdout.write(summary)

    def get_cluster(self, cluster_id):
        # if we don't have a cluster cached yet, get it
        if cluster_id not in self._clusters:
            cluster, created = Cluster.objects.get_or_create(cluster_id=cluster_id)
            # if newly created, document in log entry
            if created:
                # create a log entry
                LogEntry.objects.log_action(
                    user_id=self.script_user.pk,
                    content_type_id=self.cluster_contentype.pk,
                    object_id=cluster.pk,
                    object_repr=repr(cluster),
                    change_message="Created cluster via CSV cluster import",
                    action_flag=ADDITION,
                )
                self.stats["clusters_created"] += 1

            self._clusters[cluster_id] = cluster

        return self._clusters[cluster_id]

    # NOTE: adapted from gale_import script
    def load_csv(self, path):
        """Load a CSV file with items to be imported."""
        try:
            with open(path, encoding="utf-8-sig") as csvfile:
                csvreader = csv.DictReader(csvfile)
                data = [row for row in csvreader]
        except FileNotFoundError:
            raise CommandError("Error loading the specified CSV file: %s" % path)

        header_row = data[0].keys()
        for field in self.required_fields:
            if field not in header_row:
                raise CommandError("%s column is required in CSV file" % field)
        return data

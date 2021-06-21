from io import StringIO
import os.path

from django.core.management import call_command
from django.test import override_settings
import pymarc

from ppa.archive.gale import get_marc_record
from ppa.archive.tests.test_models import FIXTURES_PATH


def test_split_marc(tmpdir):
    marc_input = os.path.join(FIXTURES_PATH, "test_marc.dat")
    output = StringIO()
    with override_settings(MARC_DATA=tmpdir.join("marc_data")):
        call_command("split_marc", marc_input, stdout=output)
        assert "Split out 1 record from 1 file" in output.getvalue()

        # instead of testing the specifics of the implementation,
        # just test retrieval based on test id set as url in the marc record
        record = get_marc_record("CB0123456789")
        assert isinstance(record, pymarc.Record)
        assert record.title() == "Cross-platform Perl /"

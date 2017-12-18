from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
import pytest

from ppa.archive.solr import SolrSchema, CoreAdmin


@pytest.fixture
def empty_solr():
    # pytest solr fixture; updates solr schema
    with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
        # reload core before and after to ensure field list is accurate
        CoreAdmin().reload()
        solr_schema = SolrSchema()
        cp_fields = solr_schema.solr.schema.get_schema_copyfields(solr_schema.solr_collection)
        current_fields = solr_schema.solr_schema_fields()

        for cp_field in cp_fields:
            solr_schema.solr.schema.delete_copy_field(solr_schema.solr_collection, cp_field)
        for field in current_fields:
            solr_schema.solr.schema.delete_field(solr_schema.solr_collection, field)
        CoreAdmin().reload()


@pytest.fixture
def solr():
    # pytest solr fixture; updates solr schema
    with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
        # reload core before and after to ensure field list is accurate
        CoreAdmin().reload()
        SolrSchema().update_solr_schema()
        CoreAdmin().reload()


class TestSolrSchemaCommand(TestCase):

    def test_connection_error(self):
        # simulate no solr running
        with override_settings(SOLR_CONNECTIONS={'default':
                              {'COLLECTION': 'bogus',
                               'URL': 'http://localhost:191918984/solr/'}}):
            with pytest.raises(CommandError):
                call_command('solr_schema')

    @pytest.mark.skip   # skip for now - causing an error on travis-ci
    @pytest.mark.usefixtures("empty_solr")
    def test_empty_solr(self):
        with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
            output = StringIO("")
            call_command('solr_schema', stdout=output)
            output.seek(0)
            output = output.read()
            assert 'Added ' in output
            assert 'Updated ' not in output

    @pytest.mark.usefixtures("solr")
    def test_update_solr(self):
        with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
            output = StringIO("")
            call_command('solr_schema', stdout=output)
            output.seek(0)
            output = output.read()
            assert 'Updated ' in output
            assert 'Added ' not in output

from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
import pytest

from ppa.archive.forms import FacetChoiceField, SearchForm, RangeWidget, \
    RangeField
from ppa.archive.models import DigitizedWork


class TestFacetChoiceField(TestCase):

    def test_init(self):

        fcf = FacetChoiceField()
        # uses CheckboxSelectMultiple
        fcf.widget == forms.CheckboxSelectMultiple
        # not required by default
        assert not fcf.required
        # still can override required with a kwarg
        fcf = FacetChoiceField(required=True)
        assert fcf.required

    def test_valid_value(self):
        fcf = FacetChoiceField()
        # valid_value should return true
        assert fcf.valid_value('foo')


class TestSearchForm(TestCase):

    def test_init(self):
        fake_form = {'query': 'foo', 'collections': ['bar', 'baz']}
        searchform = SearchForm(fake_form)
        assert searchform.is_valid()

    def test_set_choices_from_facets(self):

        # test using a field that is configured to facet
        fake_facets = {'collections_exact': {'foo': 1, 'bar': 2}}
        searchform = SearchForm()
        # call the method to add choices to faceted field
        searchform.set_choices_from_facets(fake_facets)
        assert searchform.fields['collections'].choices[0] == \
            ('foo', 'foo <span>1</span>')
        assert searchform.fields['collections'].choices[1] == \
            ('bar', 'bar <span>2</span>')

    def test_pub_date_minmax(self):
        searchform = SearchForm()
        # no values when no data in the db
        assert searchform.pub_date_minmax() == (None, None)
        # no value should not be cached
        assert not cache.get(searchform.PUBDATE_CACHE_KEY)

        oldest = DigitizedWork.objects.create(
            title='Old Dictionary', source_id='testppa1', pub_date=1529)
        newest = DigitizedWork.objects.create(
            title='New Prosody', source_id='testppa2', pub_date=1922)

        # clear the cache
        expected = (oldest.pub_date, newest.pub_date)
        assert searchform.pub_date_minmax() == expected
        # cache value should be populated
        assert cache.get(searchform.PUBDATE_CACHE_KEY)

        # cache value should be used even if db changes
        DigitizedWork.objects.create(
            title='OldProsody', source_id='testppa3', pub_date=1523)
        assert searchform.pub_date_minmax() == expected


# range widget and field tests copied from derrida, like the objects tested

def test_range_widget():
    # range widget decompress logic
    assert RangeWidget().decompress('') == [None, None]
    # not sure how it actually handles missing inputs...
    # assert RangeWidget().decompress('100-') == [100, None]
    # assert RangeWidget().decompress('-250') == [None, 250]
    assert RangeWidget().decompress('100-250') == [100, 250]


def test_range_field():
    # range widget decompress logic
    assert RangeField().compress([]) == ''
    assert RangeField().compress([100, None]) == '100-'
    assert RangeField().compress([None, 250]) == '-250'
    assert RangeField().compress([100, 250]) == '100-250'

    # out of order should raise exception
    with pytest.raises(ValidationError):
        RangeField().compress([200, 100])

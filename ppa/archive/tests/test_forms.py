from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
import pytest

from ppa.archive.forms import FacetChoiceField, SearchForm, RangeWidget, \
    RangeField
from ppa.archive.models import DigitizedWork
from ppa.archive.forms import FacetChoiceField, SearchForm, RadioSelectWithDisabled


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

    def test_has_keyword_query(self):
        # no data
        assert not SearchForm().has_keyword_query({})
        # non keyword fields
        assert not SearchForm().has_keyword_query({'pub_date_0': 1800})
        # any of query, title, author
        assert SearchForm().has_keyword_query({'query': 'prometheus'})
        assert SearchForm().has_keyword_query({'title': 'elocution'})
        assert SearchForm().has_keyword_query({'author': 'bell'})
        # multiple
        assert SearchForm().has_keyword_query({'query': 'reading', 'title': 'elocution'})


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


def test_get_solr_fields():
    searchform = SearchForm()

    # try relevance, should return values from dictionaries to set
    # solr sort field and form/template field
    sort, solr_sort = searchform.get_solr_sort_field('relevance')
    assert sort == dict(searchform.SORT_CHOICES)['relevance']
    assert solr_sort == 'score desc'
    # try pub_date_asc, should return fields w/o score and set
    # form template field correctly
    sort, solr_sort = searchform.get_solr_sort_field('pub_date_asc')
    assert sort == dict(searchform.SORT_CHOICES)['pub_date_asc']
    assert solr_sort == 'pub_date asc'


class TestRadioWithDisabled(TestCase):

    def setUp(self):

        class TestForm(forms.Form):
            '''Build a test form use the widget'''
            CHOICES = (
                ('no', {'label': 'no select', 'disabled': True}),
                ('yes', 'yes can select'),
            )

            yes_no = forms.ChoiceField(choices=CHOICES,
                widget=RadioSelectWithDisabled)

        self.form = TestForm()

    def test_create_option(self):

        rendered = self.form.as_p()
        # no is disabled
        self.assertInHTML('<input type="radio" name="yes_no" value="no" '
                          'required id="id_yes_no_0" disabled="disabled" />',
                          rendered)
        # yes is not disabled
        self.assertInHTML('<input type="radio" name="yes_no" value="yes" '
                          'required id="id_yes_no_1" />', rendered)


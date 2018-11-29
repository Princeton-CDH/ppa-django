from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
import pytest

from ppa.archive.forms import FacetChoiceField, SearchForm, RangeWidget, \
    RangeField, RadioSelectWithDisabled, ModelMultipleChoiceFieldWithEmpty
from ppa.archive.models import DigitizedWork, Collection


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

    def setUp(self):
        # create db collections for collection choice field
        Collection.objects.bulk_create([
            Collection(name='foo'),
            Collection(name='bar'),
            Collection(name='baz'),
            Collection(name='empty'),
        ])


    def test_init(self):
        # requires collection ids because we are using model choice field
        collections = Collection.objects.all()
        fake_form = {'query': 'foo', 'collections': [collections[0].pk, collections[1].pk]}
        searchform = SearchForm(fake_form)
        assert searchform.is_valid()

    def test_defaults(self):
        defaults = SearchForm.defaults()
        assert defaults['sort'] == 'title_asc'
        # all collections should be selected, since none are set to exclude
        assert defaults['collections'] == \
            [ModelMultipleChoiceFieldWithEmpty.EMPTY_ID] + \
            list(Collection.objects.all().values_list('id', flat=True))

        Collection.objects.filter(name='empty').update(exclude=True)
        defaults = SearchForm.defaults()
        assert Collection.objects.get(name='empty').pk not in \
            defaults['collections']

    def test_collection_choices(self):
        # test collection set to disabled based on solr facets

        fake_facets = {'collections_exact': {'foo': 1, 'bar': 2, 'baz': 3}}
        searchform = SearchForm()
        # call the method to configure choices based on facets
        searchform.set_choices_from_facets(fake_facets)
        for choice in searchform.fields['collections'].widget.choices:
            # choice is index id, label
            choice_name = choice[1]
            if choice_name in ['foo', 'bar', 'baz']:
                assert isinstance(choice_name, str)
            # disabled uses override of dictionary with label and disabled flag
            else:
                assert choice_name['label'] == 'empty'
                assert choice_name['disabled']

        # old facet field behavior with facet counts, no longer
        # used for collections (but possible used in future...)

        # test using a field that is configured to facet
        # assert searchform.fields['collections'].choices[0] == \
        #     ('foo', 'foo <span>1</span>')
        # assert searchform.fields['collections'].choices[1] == \
        #     ('bar', 'bar <span>2</span>')

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
    solr_sort = searchform.get_solr_sort_field('relevance')
    assert solr_sort == 'score desc'
    # try pub_date_asc, should return fields w/o score and set
    # form template field correctly
    solr_sort = searchform.get_solr_sort_field('pub_date_asc')
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


class TestModelMultipleChoiceFieldWithEmpty(TestCase):
    fixtures = ['sample_digitized_works']

    def test_clean(self):
        collections = ModelMultipleChoiceFieldWithEmpty(
            queryset=Collection.objects.order_by('name'), label='Collection')

        # empty value -  should return empty list, no errors
        assert not collections.clean([''])

        # empty id + valid pk = should return empty label + collection
        coll1 = Collection.objects.first()
        cleaned_values = collections.clean([ModelMultipleChoiceFieldWithEmpty.EMPTY_ID,
                                            coll1.pk])
        assert collections.EMPTY_VALUE in cleaned_values
        assert coll1 in cleaned_values

        # invalid pk should still raise an exception
        with pytest.raises(ValidationError):
            collections.clean([404])



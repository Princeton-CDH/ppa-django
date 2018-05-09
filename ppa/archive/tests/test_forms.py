from django import forms
from django.test import TestCase

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

    def test_get_solr_fields(self):
        searchform = SearchForm()

        # try relevance, should return values from dictionaries to set
        # solr sort field and form/template field
        sort, solr_sort, fields = searchform.get_solr_sort_field('relevance')
        assert sort == dict(searchform.SORT_CHOICES)['relevance']
        assert solr_sort == 'score desc'
        assert fields == '*,score'
        # try pub_date_asc, should return fields w/o score and set
        # form template field correctly
        sort, solr_sort, fields = searchform.get_solr_sort_field('pub_date_asc')
        assert sort == dict(searchform.SORT_CHOICES)['pub_date_asc']
        assert solr_sort == 'pub_date asc'
        assert fields == '*'

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

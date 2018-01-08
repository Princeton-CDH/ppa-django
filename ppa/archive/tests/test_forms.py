from django import forms
from django.test import TestCase

from ppa.archive.forms import FacetChoiceField, SearchForm


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

from django import forms
from django.utils.safestring import mark_safe

from ppa.archive.models import Collection

class FacetChoiceField(forms.MultipleChoiceField):
    '''Add CheckboxSelectMultiple field with facets taken from solr query'''
    # Borrowed from https://github.com/Princeton-CDH/derrida-django/blob/develop/derrida/books/forms.py
    # customize multiple choice field for use with facets.
    # no other adaptations needed
    # - turn of choice validation (shouldn't fail if facets don't get loaded)
    # - default to not required
    # - use checkbox select multiple as default widget

    widget = forms.CheckboxSelectMultiple

    def __init__(self, *args, **kwargs):
        if 'required' not in kwargs:
            kwargs['required'] = False
        super(FacetChoiceField, self).__init__(*args, **kwargs)

    def valid_value(self, value):
        return True


class SearchForm(forms.Form):
    '''Simple search form for digitized works.'''
    query = forms.CharField(label='Search', required=False)
    collections = FacetChoiceField()

    # fields to request a facet from solr
    facet_fields = ['collections_exact']

    # mapping of solr fields to form input
    solr_facet_fields = {
        'collections_exact': 'collections'
    }

    def set_choices_from_facets(self, facets):
        '''Set choices on field from a dictionary of facets'''
        # Also borrowed from Derrida module referenced for FacetChoiceField
        # Uses mapping of solr_facet_fields and facet_fields in class
        # definition but does not yet import full functionality of
        # derrida-django's ReferenceSearchForm

        # The primary adaptation involves use of a dictionary of dictionaries
        # for facets in SolrClient vs. the functionality of
        # django-haystack/pysolr.
        for key, facet_dict in facets.items():
            formfield = self.solr_facet_fields.get(key, key)
            if formfield in self.fields:
                self.fields[formfield].choices = [
                    (val, mark_safe('%s <span>%d</span>' % (val, count)))
                    for val, count in facet_dict.items()]


class AddToCollectionForm(forms.Form):
    '''
    Form to select a set of :class:ppa.archive.models.Collection to which
    to bulk add a queryset of :class:ppa.archive.models.DigitizedWork
    '''

    collections = forms.ModelMultipleChoiceField(
        required=True, queryset=Collection.objects.all().order_by('name'),
        help_text='Hold down ctrl or command key (on MacOS) to select '
                  'multiple collections.')

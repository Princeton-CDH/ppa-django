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

    SORT_CHOICES = [
        ('relevance', 'relevance'),
        ('pub_date_asc', 'chronology (earliest to latest)'),
        ('pub_date_desc', 'chronology (latest to earliest)'),
        ('title_asc', 'title (A to Z)'),
        ('title_desc', 'title (Z to A)'),
        ('author_asc', 'author (A to Z)'),
        ('author_desc', 'author (Z to A)'),
    ]

    def __init__(self, *args, **kwargs):
        '''
        Set choices dynamically based on form kwargs and presence of keywords.
        '''
        super(SearchForm, self).__init__(*args, **kwargs)
        if not args or 'query' not in args[0] or not args[0]['query']:
            # if there aren't keywords to search for, this will remove
            # relevance from the form choices
            self.fields['sort'].choices = self.fields['sort'].choices[1:]

    query = forms.CharField(label='Search', required=False)
    collections = FacetChoiceField()
    sort = forms.ChoiceField(widget=forms.RadioSelect, choices=SORT_CHOICES,
        required=False)
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

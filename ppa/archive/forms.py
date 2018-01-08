from django import forms
from django.utils.safestring import mark_safe


class FacetChoiceField(forms.MultipleChoiceField):
    '''Add CheckboxSelectMultiple field with facets taken from solr query'''
    # customize multiple choice field for use with facets
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
        for key, facet_dict in facets.items():
            formfield = self.solr_facet_fields.get(key, key)
            if formfield in self.fields:
                self.fields[formfield].choices = [
                    (val, mark_safe('%s <span>%d</span>' % (val, count)))
                    for val, count in facet_dict.items()]

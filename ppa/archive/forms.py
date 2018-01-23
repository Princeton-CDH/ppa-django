from django import forms


class SearchForm(forms.Form):
    '''Simple search form for digitized works.'''
    query = forms.CharField(label='Search', required=False)

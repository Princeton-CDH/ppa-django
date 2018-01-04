from django import forms
from ppa.archive.models import Collection


class SearchForm(forms.Form):
    query = forms.CharField(label='Search', required=False)
    collections = forms.ModelMultipleChoiceField(
        label='Collections',
        queryset=Collection.objects.all(),
        required=False
    )

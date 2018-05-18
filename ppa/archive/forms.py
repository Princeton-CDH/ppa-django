from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import Max, Min
from django.utils.safestring import mark_safe


from ppa.archive.models import Collection, DigitizedWork


class RadioSelectWithDisabled(forms.RadioSelect):
    '''
    Subclass of :class:`django.forms.RadioSelect` that takes a label override
    in the widget's choice label option in the form a dictionary:
    {'label': 'option', 'disabled': True}.
    '''

    # Using a solution at https://djangosnippets.org/snippets/2453/
    def create_option(self, name, value, label, selected, index, subindex=None,
                      attrs=None):
        disabled = None
        if isinstance(label, dict):
            label, disabled = label['label'], label['disabled']
        option_dict = super().create_option(
                name, value, label, selected, index,
                subindex=subindex, attrs=attrs
            )
        if disabled:
            option_dict['attrs'].update({'disabled': 'disabled'})
        return option_dict


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
        super().__init__(*args, **kwargs)

    def valid_value(self, value):
        return True


# RangeWidget and RangeField also borrowed from Derrida codebase

class RangeWidget(forms.MultiWidget):
    '''date range widget, for two numeric inputs'''

    #: separator string when splitting out values in decompress
    sep = '-'
    #: template to use to render range multiwidget
    # (based on multiwidget, but adds "to" between dates)
    template_name = 'archive/widgets/rangewidget.html'

    def __init__(self, *args, **kwargs):
        widgets = [
            forms.NumberInput(),
            forms.NumberInput()
        ]
        super().__init__(widgets, *args, **kwargs)

    def decompress(self, value):
        if value:
            return [int(val) for val in value.split(self.sep)]
        return [None, None]


class RangeField(forms.MultiValueField):
    widget = RangeWidget

    def __init__(self, *args, **kwargs):
        fields = (
            forms.IntegerField(
                error_messages={'invalid': 'Enter a number'},
                validators=[
                    RegexValidator(r'^[0-9]*$', 'Enter a valid number.'),
                ],
                required=False
            ),
            forms.IntegerField(
                error_messages={'invalid': 'Enter a number'},
                validators=[
                    RegexValidator(r'^[0-9]*$', 'Enter a valid number.'),
                ],
                required=False
            ),
        )
        kwargs['fields'] = fields
        super().__init__(require_all_fields=False, *args, **kwargs)


    def compress(self, data_list):
        # if both values are set and the first is greater than the second,
        # raise a validation error
        if all(data_list) and len(data_list) == 2 and data_list[0] > data_list[1]:
            raise ValidationError('Invalid range (%s - %s)' % (data_list[0], data_list[1]))
        return self.widget.sep.join(['%d' % val if val else '' for val in data_list])


class SearchForm(forms.Form):
    '''Simple search form for digitized works.'''

    SORT_CHOICES = [
        ('relevance', 'Relevance'),
        ('pub_date_asc', 'Year Oldest-Newest'),
        ('pub_date_desc', 'Year Newest-Oldest'),
        ('title_asc', 'Title A-Z'),
        ('title_desc', 'Title Z-A'),
        ('author_asc', 'Author A-Z'),
        ('author_desc', 'Author Z-A'),
    ]

    defaults = {
        'sort': 'title_asc',
    }

    # this appears when you hover over the question mark icon
    QUESTION_POPUP_TEXT = mark_safe('''
    Boolean search within a field is supported. Operators must be capitalized (AND, OR).
    ''')

    # text inputs
    query = forms.CharField(label='Keyword or Phrase', required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search the full text and metadata of the archive',
            '_icon': 'search',
            '_align': 'left'
        }))
    title = forms.CharField(label='Book Title', required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search the archive by book title',
            '_icon': 'search',
            '_align': 'left'
        }))
    author = forms.CharField(label='Author', required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search the archive by author',
            '_icon': 'search',
            '_align': 'left'
        }))

    # facets
    collections = FacetChoiceField(label='Collection')
    pub_date = RangeField(label='Publication Year', required=False,
        widget=RangeWidget(attrs={
            'size': 4,
            '_inline': True
        }))

    sort = forms.ChoiceField(widget=RadioSelectWithDisabled, choices=SORT_CHOICES,
        required=False)
    # booleans
    earliest_only = forms.BooleanField(label='Earliest Edition in Hathi',
        required=False, widget=forms.CheckboxInput(attrs={
            '_icon': 'flag outline', 'disabled': True
        }))
    ace_only = forms.BooleanField(label='Authorized Critical Edition',
        required=False, widget=forms.CheckboxInput(attrs={
            '_icon': 'flag', 'disabled': True
        }))
    dict_exclude = forms.BooleanField(label='Dictionaries',
        required=False, widget=forms.CheckboxInput(attrs={'disabled': True}))
    pg_exclude = forms.BooleanField(label='Pronunciation Guides',
        required=False, widget=forms.CheckboxInput(attrs={'disabled': True}))
    # fields to request a facet from solr
    facet_fields = ['collections_exact']
    range_facets = ['pub_date']

    # mapping of solr fields to form input
    solr_facet_fields = {
        'collections_exact': 'collections'
    }

    def __init__(self, data=None, *args, **kwargs):
        '''
        Set choices dynamically based on form kwargs and presence of keywords.
        '''
        super().__init__(data=data, *args, **kwargs)

        pubdate_range = self.pub_date_minmax()
        # because pubdate is a multifield/multiwidget, access the widgets
        # under the multiwidgets
        pubdate_widgets = self.fields['pub_date'].widget.widgets
        for idx, val in enumerate(pubdate_range):
            # don't set None as placeholder (only possible if db is empty)
            if val:
                # set placeholder and max/min values
                pubdate_widgets[idx].attrs.update({'placeholder': val,
                    'min': pubdate_range[0], 'max': pubdate_range[1]})

        # relevance is disabled unless we have a keyword query present
        if not data or not self.has_keyword_query(data):
            self.fields['sort'].widget.choices[0] = \
                ('relevance', {'label': 'Relevance', 'disabled': True})

    def has_keyword_query(self, data):
        '''check if any of the keyword search fields have search terms'''
        return any(data.get(query_field, None)
                   for query_field in ['query', 'title', 'author'])

    def get_solr_sort_field(self, sort):
        '''
        Set solr sort fields for the query based on sort and query strings.

        :return: solr sort field
        '''
        solr_mapping = {
            'relevance': 'score desc',
            'pub_date_asc': 'pub_date asc',
            'pub_date_desc': 'pub_date desc',
            'title_asc': 'title_exact asc',
            'title_desc': 'title_exact desc',
            'author_asc': 'author_exact asc',
            'author_desc': 'author_exact desc',
        }
        # return solr field for requested sort option
        return solr_mapping[sort]

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


    PUBDATE_CACHE_KEY = 'digitizedwork_pubdate_maxmin'

    def pub_date_minmax(self):
        '''Get minimum and maximum values for
        :class:`~ppa.archive.models.DigitizedWork` publication dates
        in the database.  Used to set placeholder values for the form
        input and to generate the Solr facet range query.
        Value is cached to avoid repeatedly calculating it.

        :returns: tuple of min, max
        '''
        maxmin = cache.get(self.PUBDATE_CACHE_KEY)
        if not maxmin:
            maxmin = DigitizedWork.objects \
                .aggregate(Max('pub_date'), Min('pub_date'))

            # cache as returned from django; looks like this:
            # {'pub_date__max': 1922, 'pub_date__min': 1559}

            # don't cache if values are None
            # should only happen if no data is in the db
            if all(maxmin.values()):
                cache.set(self.PUBDATE_CACHE_KEY, maxmin)

        # return just the min and max values
        return maxmin['pub_date__min'], maxmin['pub_date__max']



class AddToCollectionForm(forms.Form):
    '''
    Form to select a set of :class:ppa.archive.models.Collection to which
    to bulk add a queryset of :class:ppa.archive.models.DigitizedWork
    '''

    collections = forms.ModelMultipleChoiceField(
        required=True, queryset=Collection.objects.all().order_by('name'),
        help_text='Hold down ctrl or command key (on MacOS) to select '
                  'multiple collections.')

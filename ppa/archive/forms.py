from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import Max, Min

from ppa.archive.models import NO_COLLECTION_LABEL, Collection, DigitizedWork
from ppa.common.utils import simplify_quotes


class ChoiceLabel:
    """Custom choice label that can be used to set an option as disabled
    without resulting in extra choices when normalized."""

    def __init__(self, label, disabled=False):
        self.label = label
        self.disabled = disabled

    def __str__(self):
        return str(self.label)


class SelectDisabledMixin(object):
    """
    Mixin for :class:`django.forms.RadioSelect` or :class:`django.forms.CheckboxSelect`
    classes to set an option as disabled. To disable, the widget's choice
    label option should be passed in as a dictionary with `disabled` set
    to True::

        {'label': 'option', 'disabled': True}.
    """

    # Using a solution at https://djangosnippets.org/snippets/2453/
    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        """Overide option creation to optionally disable specified values"""
        disabled = None

        if isinstance(label, dict):
            label, disabled = label["label"], label.get("disabled", False)
        elif isinstance(label, ChoiceLabel):
            disabled = label.disabled

        option_dict = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        if disabled:
            option_dict["attrs"].update({"disabled": "disabled"})
        return option_dict


class RadioSelectWithDisabled(SelectDisabledMixin, forms.RadioSelect):
    """
    Subclass of :class:`django.forms.RadioSelect` with option to mark
    a choice as disabled.
    """


class SelectWithDisabled(SelectDisabledMixin, forms.Select):
    """
    Subclass of :class:`django.forms.Select` with option to mark
    a choice as disabled.
    """


class CheckboxSelectMultipleWithDisabled(
    SelectDisabledMixin, forms.CheckboxSelectMultiple
):
    """
    Subclass of :class:`django.forms.CheckboxSelectMultiple` with option to mark
    a choice as disabled.
    """


class CollectionCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value and value.instance.digwork_count == 0:
            option["attrs"]["disabled"] = "disabled"
        return option


class FacetChoiceField(forms.MultipleChoiceField):
    """Add CheckboxSelectMultiple field with facets taken from solr query"""

    # Borrowed from https://github.com/Princeton-CDH/derrida-django/blob/develop/derrida/books/forms.py
    # customize multiple choice field for use with facets.
    # no other adaptations needed
    # - turn of choice validation (shouldn't fail if facets don't get loaded)
    # - default to not required
    # - use checkbox select multiple as default widget

    widget = forms.CheckboxSelectMultiple

    def __init__(self, *args, **kwargs):
        if "required" not in kwargs:
            kwargs["required"] = False
        super().__init__(*args, **kwargs)

    def valid_value(self, value):
        return True


# RangeWidget and RangeField also borrowed from Derrida codebase


class RangeWidget(forms.MultiWidget):
    """date range widget, for two numeric inputs"""

    #: separator string when splitting out values in decompress
    sep = "-"
    #: template to use to render range multiwidget
    # (based on multiwidget, but adds "to" between dates)
    template_name = "archive/widgets/rangewidget.html"

    def __init__(self, *args, **kwargs):
        widgets = [
            forms.NumberInput(attrs={"aria-label": "Start"}),
            forms.NumberInput(attrs={"aria-label": "End"}),
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
                error_messages={"invalid": "Enter a number"},
                validators=[
                    RegexValidator(r"^[0-9]*$", "Enter a valid number."),
                ],
                required=False,
            ),
            forms.IntegerField(
                error_messages={"invalid": "Enter a number"},
                validators=[
                    RegexValidator(r"^[0-9]*$", "Enter a valid number."),
                ],
                required=False,
            ),
        )
        kwargs["fields"] = fields
        super().__init__(require_all_fields=False, *args, **kwargs)

    def compress(self, data_list):
        # if both values are set and the first is greater than the second,
        # raise a validation error
        if all(data_list) and len(data_list) == 2 and data_list[0] > data_list[1]:
            raise ValidationError(
                "Invalid range (%s - %s)" % (data_list[0], data_list[1])
            )
        return self.widget.sep.join(["%d" % val if val else "" for val in data_list])


class ModelMultipleChoiceFieldWithEmpty(forms.ModelMultipleChoiceField):
    """Extend :class:`django.forms.ModelMultipleChoiceField` to add an
    option for an unset or empty choice (i.e. no relationship in a
    many-to-many relationship such as collection membership).
    """

    EMPTY_VALUE = NO_COLLECTION_LABEL
    EMPTY_ID = 0

    def clean(self, value):
        """Extend clean to use default validation on all values but
        the empty id."""
        try:
            pk_values = [val for val in value if val and int(val) != self.EMPTY_ID]
        except ValueError:
            # non-integer will raise value error
            raise ValidationError("Invalid collection")
        qs = super()._check_values(pk_values)
        if self.EMPTY_ID in value or str(self.EMPTY_ID) in value:
            return [self.EMPTY_VALUE] + list(qs)
        return qs


class SearchForm(forms.Form):
    """Simple search form for digitized works."""

    SORT_CHOICES = [
        ("relevance", "Relevance"),
        ("pub_date_asc", "Year Oldest-Newest"),
        ("pub_date_desc", "Year Newest-Oldest"),
        ("title_asc", "Title A-Z"),
        ("title_desc", "Title Z-A"),
        ("author_asc", "Author A-Z"),
        ("author_desc", "Author Z-A"),
    ]

    #: help text to be shown with the form
    #: (appears when you hover over the question mark icon)
    QUESTION_POPUP_TEXT = """
    Boolean search within a field is supported. Operators must be capitalized (AND, OR).
    Use quotes for exact phrase.
    """

    # text inputs
    query = forms.CharField(
        label="Keyword or Phrase",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search full-text and metadata, including approximate titles.",
                "_icon": "search",
                "_align": "left",
            }
        ),
    )
    title = forms.CharField(
        label="Title",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by exact title or subtitle.",
                "_icon": "search",
                "_align": "left",
            }
        ),
    )
    author = forms.CharField(
        label="Author",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by exact author (last name, first name).",
                "_icon": "search",
                "_align": "left",
            }
        ),
    )

    # facets
    # collections = FacetChoiceField(label='Collection')
    # NOTE: using model choice field to list all collections in the database,
    # even if they have no assocaited works in Solr
    collections = ModelMultipleChoiceFieldWithEmpty(
        queryset=Collection.objects.order_by("name"),
        label="Collection",
        widget=CheckboxSelectMultipleWithDisabled,
        # widget=CollectionCheckboxSelectMultiple,
        required=False,
    )
    pub_date = RangeField(
        label="Publication Date",
        required=False,
        widget=RangeWidget(
            attrs={"size": 4, "title": "publication date", "_inline": True}
        ),
    )

    #: hidden input to track cluster id, for searching within reprint/editions
    cluster = forms.CharField(widget=forms.HiddenInput(), required=False)

    sort = forms.ChoiceField(
        widget=SelectWithDisabled, choices=SORT_CHOICES, required=False
    )

    # booleans
    earliest_only = forms.BooleanField(
        label="Earliest Edition in Hathi",
        required=False,
        widget=forms.CheckboxInput(attrs={"disabled": True}),
    )
    ace_only = forms.BooleanField(
        label="Authorized Critical Edition",
        required=False,
        widget=forms.CheckboxInput(attrs={"disabled": True}),
    )
    dict_exclude = forms.BooleanField(
        label="Dictionaries",
        required=False,
        widget=forms.CheckboxInput(attrs={"disabled": True}),
    )
    pg_exclude = forms.BooleanField(
        label="Pronunciation Guides",
        required=False,
        widget=forms.CheckboxInput(attrs={"disabled": True}),
    )
    # fields to request a facet from solr
    facet_fields = ["collections_exact"]
    range_facets = ["pub_date"]

    # mapping of solr fields to form input
    solr_facet_fields = {"collections_exact": "collections"}

    @staticmethod
    def defaults():
        """Default values when initializing the form.  Sort by title,
        pre-select collections based exclude property."""
        return {
            "sort": "title_asc",
            # always include uncategorized collections; no harm if not present
            "collections": [ModelMultipleChoiceFieldWithEmpty.EMPTY_ID]
            + list(
                Collection.objects.filter(exclude=False).values_list("id", flat=True)
            ),
        }

    def __init__(self, data=None, *args, **kwargs):
        """
        Set choices dynamically based on form kwargs and presence of keywords.
        """
        super().__init__(data=data, *args, **kwargs)

        pubdate_range = self.pub_date_minmax()
        self.pubdate_validation_msg = (
            "Enter sequential years between {} and {}.".format(
                pubdate_range[0], pubdate_range[1]
            )
        )
        # because pubdate is a multifield/multiwidget, access the widgets
        # under the multiwidgets
        pubdate_widgets = self.fields["pub_date"].widget.widgets
        for idx, val in enumerate(pubdate_range):
            # don't set None as placeholder (only possible if db is empty)
            if val:
                # set max/min and initial values
                pubdate_widgets[idx].attrs.update(
                    {
                        "placeholder": pubdate_range[idx],
                        "min": pubdate_range[0],
                        "max": pubdate_range[1],
                    }
                )

        # relevance is disabled unless we have a keyword query present
        if not data or not self.has_keyword_query(data):
            self.fields["sort"].widget.choices[0] = (
                "relevance",
                {"label": "Relevance", "disabled": True},
            )

    def has_keyword_query(self, data):
        """check if any of the keyword search fields have search terms"""
        return any(
            data.get(query_field, None) for query_field in ["query", "title", "author"]
        )

    def get_solr_sort_field(self, sort=None):
        """
        Set solr sort fields for the query based on sort and query strings.
        If sort field is not specified, will use sort in the the cleaned
        data in the current form. If sort is not specified and valid
        form data is not available, will raise an :class:`AttributeError`.

        :return: solr sort field
        """
        solr_mapping = {
            "relevance": "-score",
            "pub_date_asc": "pub_date",
            "pub_date_desc": "-pub_date",
            "title_asc": "sort_title",
            "title_desc": "-sort_title",
            "author_asc": "author_exact",
            "author_desc": "-author_exact",
        }
        # if not specified, use sort value from current form data
        if sort is None:
            sort = self.cleaned_data.get("sort")
        # return solr field for requested sort option
        return solr_mapping.get(sort, None)

    def set_choices_from_facets(self, facets):
        """Set choices on field from a dictionary of facets"""

        # update collections multiselect based on facets

        for facet_field, form_field in self.solr_facet_fields.items():
            # currently the only configured facet field
            if form_field == "collections":
                self.fields["collections"].widget
                facet_dict = facets[facet_field]
                solr_collections = facet_dict.keys()

                # construct updated choice list
                choices = []
                # iterate over existing choices (based on collections in database)
                # widget choice is tuple of ModelChoiceIteratorValue, name
                for itervalue, label in self.fields[form_field].widget.choices:
                    # if a collection is not in solr, mark it as disabled
                    if label not in solr_collections:
                        # we have to use ChoiceLabel here instead of a dict
                        # to avoid dict values being normalized into choices
                        choices.append((itervalue, ChoiceLabel(label, disabled=True)))
                    # otherwise, add choice unchanged
                    else:
                        choices.append((itervalue, label))

                # if there are any items not in a collection, add an option
                # so they will be findable
                if NO_COLLECTION_LABEL in facet_dict:
                    choices.append(
                        (
                            ModelMultipleChoiceFieldWithEmpty.EMPTY_ID,
                            NO_COLLECTION_LABEL,
                        )
                    )

                # replace form field choices with updated options
                # Note that setting here updates both field and widget;
                # it runs through a normalize method, which is why
                # we can't use a dict for label + disabled
                self.fields[form_field].choices = choices

    PUBDATE_CACHE_KEY = "digitizedwork_pubdate_maxmin"

    def pub_date_minmax(self):
        """Get minimum and maximum values for
        :class:`~ppa.archive.models.DigitizedWork` publication dates
        in the database.  Used to set placeholder values for the form
        input and to generate the Solr facet range query.
        Value is cached to avoid repeatedly calculating it.

        :returns: tuple of min, max
        """
        maxmin = cache.get(self.PUBDATE_CACHE_KEY)
        if not maxmin:
            maxmin = DigitizedWork.objects.aggregate(Max("pub_date"), Min("pub_date"))

            # cache as returned from django; looks like this:
            # {'pub_date__max': 1922, 'pub_date__min': 1559}

            # don't cache if values are None
            # should only happen if no data is in the db
            if all(maxmin.values()):
                cache.set(self.PUBDATE_CACHE_KEY, maxmin)

        # return just the min and max values
        return maxmin["pub_date__min"], maxmin["pub_date__max"]

    def _clean_quotes(self, field):
        value = self.cleaned_data.get(field)
        if value:
            return simplify_quotes(value)
        return value  # return since could be None or empty string

    # query, author, and title could all have quotes for exact phrase

    def clean_query(self):
        """Clean keyword search query term; converts any typographic
        quotes to straight quotes"""
        return self._clean_quotes("query")

    def clean_title(self):
        """Clean keyword search query term; converts any typographic
        quotes to straight quotes"""
        return self._clean_quotes("title")

    def clean_author(self):
        """Clean keyword search query term; converts any typographic
        quotes to straight quotes"""
        return self._clean_quotes("author")


class SearchWithinWorkForm(forms.Form):
    """
    Form to search for occurrences of a string within a particular instance
    of a digitized work.
    """

    #: help text to be shown with the form
    #: (appears when you hover over the question mark icon)
    QUESTION_POPUP_TEXT = """
    Boolean search is supported. Operators must be capitalized (AND, OR).
    """

    # single text input
    query = forms.CharField(
        label="Search within the Volume",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search keyword or phrase",
                "_icon": "search",
                "_align": "left",
            }
        ),
    )


class AddToCollectionForm(forms.Form):
    """
    Form to select a set of :class:ppa.archive.models.Collection to which
    to bulk add a queryset of :class:ppa.archive.models.DigitizedWork
    """

    collections = forms.ModelMultipleChoiceField(
        required=True,
        queryset=Collection.objects.all().order_by("name"),
        help_text="Hold down ctrl or command key (on MacOS) to select "
        "multiple collections.",
    )


class ImportForm(forms.Form):
    """Form to import records from sources that support import."""

    # only a subset of DigitizedWork.SOURCE_CHOICES can be imported
    importable_sources = (
        (DigitizedWork.HATHI, "HathiTrust"),
        (DigitizedWork.GALE, "Gale"),
    )

    source = forms.ChoiceField(
        label="Source",
        choices=importable_sources,
        help_text="Where should records be imported from?",
        required=True,
        widget=forms.RadioSelect,
    )

    source_ids = forms.CharField(
        label="Record Identifiers",
        required=True,
        widget=forms.Textarea,
        help_text="List of source IDs for items to add, one per line. "
        + "Existing records and invalid IDs will be skipped.",
    )

    def get_source_ids(self):
        """Get list of ids from valid form input. Splits on newlines,
        strips whitespace, and ignores empty lines."""
        return [
            line.strip()
            for line in self.cleaned_data["source_ids"].split("\n")
            if line.strip()
        ]

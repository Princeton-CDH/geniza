import re

from dal import autocomplete
from django import forms
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.db.models import Count
from django.template.loader import get_template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from taggit.models import Tag

from geniza.common.fields import RangeField, RangeForm, RangeWidget
from geniza.common.utils import simplify_quotes
from geniza.corpus.models import Document, DocumentType
from geniza.entities.models import DocumentPlaceRelation, PersonDocumentRelation


class SelectDisabledMixin:
    """
    Mixin for :class:`django.forms.RadioSelect` or :class:`django.forms.CheckboxSelect`
    classes to set an option as disabled. To disable, the widget's choice
    label option should be passed in as a dictionary with `disabled` set
    to True::
        {'label': 'option', 'disabled': True}.
    """

    # copied from mep-django

    # Using a solution at https://djangosnippets.org/snippets/2453/
    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        disabled = None

        if isinstance(label, dict):
            label, disabled = label["label"], label.get("disabled", False)
        option_dict = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        if disabled:
            option_dict["attrs"].update({"disabled": "disabled"})
        return option_dict


class SelectWithDisabled(SelectDisabledMixin, forms.Select):
    """
    Subclass of :class:`django.forms.Select` with option to mark
    a choice as disabled.
    """


class WidgetCountMixin:
    # extend default choice field widgets to add facet counts and
    # include per-item count as a data attribute
    facet_counts = {}

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        for optgroup in context["widget"].get("optgroups", []):
            for option in optgroup[1]:
                # each value of facet_counts is a tuple of label and count
                (label, count) = self.facet_counts.get(
                    option["value"], (option["value"], None)
                )
                # make facet count available as data-count attribute
                if count:
                    option["attrs"]["data-count"] = f"{count:,}"
        return context


class CheckboxSelectWithCount(WidgetCountMixin, forms.CheckboxSelectMultiple):
    """
    Subclass of :class:`django.forms.CheckboxSelectMultiple` with support for facet counts.
    """


class SelectWithCount(WidgetCountMixin, forms.Select):
    """
    Subclass of :class:`django.forms.Select` with support for facet counts.
    """


class FacetFieldMixin:
    # Borrowed from ppa-django / mep-django
    # - turn off choice validation (shouldn't fail if facets don't get loaded)
    # - default is not required

    def __init__(self, *args, **kwargs):
        if "required" not in kwargs:
            kwargs["required"] = False

        # get custom kwarg and remove before passing to MultipleChoiceField
        # super method, which would cause an error
        if hasattr(self.widget, "legend"):
            self.widget.legend = None
            if "legend" in kwargs:
                self.widget.legend = kwargs["legend"]
                del kwargs["legend"]

        super().__init__(*args, **kwargs)

        # if no custom legend, set it from label
        if hasattr(self.widget, "legend") and not self.widget.legend:
            self.widget.legend = self.label

    def valid_value(self, value):
        return True


class FacetChoiceField(FacetFieldMixin, forms.ChoiceField):
    """Choice field where choices are set based on Solr facets"""

    # use a custom widget so we can add facet count as a data attribute
    widget = CheckboxSelectWithCount

    def populate_from_facets(self, facet_dict):
        """
        Populate the field choices from the facets returned by solr.
        """
        # generate the list of choice from the facets

        self.choices = (
            (
                val,
                mark_safe(f'<span>{label}</span><span class="count">{count:,}</span>'),
            )
            for val, (label, count) in facet_dict.items()
        )
        # pass the counts to the widget so it can be set as a data attribute
        self.widget.facet_counts = facet_dict


class FacetChoiceSelectField(FacetFieldMixin, forms.ChoiceField):
    """Choice field where choices are set based on Solr facets"""

    # use a custom widget so we can add facet count as a data attribute
    widget = SelectWithCount
    empty_label = None

    def __init__(self, empty_label=None, *args, **kwargs):
        if empty_label:
            self.empty_label = empty_label
        super().__init__(*args, **kwargs)

    def populate_from_facets(self, facet_dict):
        """
        Populate the field choices from the facets returned by solr.
        """
        # generate the list of choice from the facets
        self.choices = (
            (
                val,
                mark_safe(
                    f'<span>{label}</span> (<span class="count">{count:,}</span>)'
                ),
            )
            for val, (label, count) in facet_dict.items()
        )
        # pass the counts to the widget so it can be set as a data attribute
        self.widget.facet_counts = facet_dict

        # add empty label if present (for <select> dropdowns)
        if self.empty_label:
            self.choices = [("", self.empty_label)] + self.choices


class CheckboxInputWithCount(forms.CheckboxInput):
    # extend default CheckboxInput to add facet count as a data attribute
    facet_counts = {}

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # each value of facet_counts is a tuple of label and count
        (label, count) = self.facet_counts.get("true", ("true", None))
        # make facet count available as data-count attribute
        if count:
            context["widget"]["attrs"]["data-count"] = f"{count:,}"
        return context


class BooleanFacetField(FacetFieldMixin, forms.BooleanField):
    widget = CheckboxInputWithCount

    def populate_from_facets(self, facet_dict):
        """
        Set the label from the facets returned by solr.
        """
        # each value of facet_counts is a tuple of label and count; boolean facet label is always
        # just "true" or "false"
        (label, count) = facet_dict.get("true", ("true", 0))
        # use self.label for the actual label instead, so we use the field name and not true/false
        self.label = mark_safe(
            f'<span class="label">{self.label}</span><span class="count">{count:,}</span>'
        )

        # pass the counts to the widget so it can be set as a data attribute
        self.widget.facet_counts = facet_dict


class YearRangeWidget(RangeWidget):
    """Extend :class:`django.forms.widgets.RangeWidget` to customize the output and add
    year start/end labels to the individual inputs."""

    template_name = "corpus/widgets/yearrangewidget.html"


class DocumentSearchForm(RangeForm):
    q = forms.CharField(
        label="Keyword or Phrase",
        required=False,
        widget=forms.TextInput(
            attrs={
                # Translators: placeholder for keyword search input
                "placeholder": _("Search all fields by keyword"),
                # Translators: accessible label for keyword search input
                "aria-label": _("Keyword or Phrase"),
                "type": "search",
                "dir": "auto",  # expect mixed ltr/rtl
            }
        ),
    )

    SORT_CHOICES = [
        # Translators: label for sort by relevance
        ("relevance", _("Relevance")),
        # Translators: label for sort in random order
        ("random", _("Random")),
        # Translators: label for sort by document date (most recent first)
        ("docdate_desc", _("Document Date (Latest–Earliest)")),
        # Translators: label for sort by document date (oldest first)
        ("docdate_asc", _("Document Date (Earliest–Latest)")),
        # Translators: label for alphabetical sort by shelfmark
        ("shelfmark", _("Shelfmark (A–Z)")),
        # Translators: label for descending sort by number of scholarship records
        ("scholarship_desc", _("Scholarship Records (Most–Least)")),
        # Translators: label for ascending sort by number of scholarship records
        ("scholarship_asc", _("Scholarship Records (Least–Most)")),
        # Translators: label for sort by when document was added to PGP (most recent first)
        ("input_date_desc", _("PGP Input Date (Latest–Earliest)")),
        # Translators: label for sort by when document was added to PGP (oldest first)
        ("input_date_asc", _("PGP Input Date (Earliest–Latest)")),
    ]
    # Translators: label for start year when filtering by date range
    _("From year")
    # Translators: label for end year when filtering by date range
    _("To year")

    MODE_CHOICES = [
        # Translators: label for general search mode
        ("general", _("General")),
        # Translators: label for regex (regular expressions) search mode
        ("regex", _("RegEx")),
    ]

    # NOTE these are not set by default!
    error_css_class = "error"
    required_css_class = "required"

    sort = forms.ChoiceField(
        # Translators: label for form sort field
        label=_("Sort by"),
        choices=SORT_CHOICES,
        required=False,
        widget=SelectWithDisabled,
    )
    docdate = RangeField(
        # Translators: label for filter documents by date range
        label=_("Dates"),
        required=False,
        widget=YearRangeWidget(
            attrs={"size": 4, "data-action": "input->search#update"},
        ),
    )

    exclude_inferred = forms.BooleanField(
        # Translators: label for "exclude inferred dates" search form filter
        label=_("Exclude inferred dates"),
        required=False,
        widget=forms.CheckboxInput,
    )

    doctype = FacetChoiceField(
        # Translators: label for document type search form filter
        label=_("Document type"),
    )
    has_image = BooleanFacetField(
        # Translators: label for "has image" search form filter
        label=_("Image"),
    )
    has_transcription = BooleanFacetField(
        # Translators: label for "has transcription" search form filter
        label=_("Transcription"),
    )
    has_translation = BooleanFacetField(
        # Translators: label for "has translation" search form filter
        label=_("Translation"),
    )
    has_discussion = BooleanFacetField(
        # Translators: label for "has discussion" search form filter
        label=_("Discussion"),
    )
    translation_language = FacetChoiceSelectField(
        # Translators: label for document translation language search form filter
        label=_("Translation language"),
        widget=SelectWithCount,
        empty_label=_("All languages"),
    )

    mode = forms.ChoiceField(
        # Translators: label for "search mode" (general or regex)
        label=_("Search mode"),
        choices=MODE_CHOICES,
        required=False,
        widget=forms.RadioSelect,
    )

    # mapping of solr facet fields to form input
    solr_facet_fields = {
        "type": "doctype",
        "has_digital_edition": "has_transcription",
        "has_digital_translation": "has_translation",
        "has_discussion": "has_discussion",
    }

    def __init__(self, data=None, *args, **kwargs):
        """
        Override to set choices dynamically based on form kwargs.
        """
        super().__init__(data=data, *args, **kwargs)

        # if a keyword search term is not present, relevance sort is disabled
        if not data or not data.get("q", None):
            self.fields["sort"].widget.choices[0] = (
                self.SORT_CHOICES[0][0],
                {"label": self.SORT_CHOICES[0][1], "disabled": True},
            )

        # if "has translation" is not selected, language dropdown is disabled
        if not data or not data.get("has_translation", None):
            self.fields["translation_language"].disabled = True

    def get_translated_label(self, field, label):
        """Lookup translated label via db model object when applicable;
        handle Person.gender as a special case; and otherwise just return the label"""
        if field == "type" or field == "doctype":
            # for doctype, label should be translated, so use doctype object
            return DocumentType.objects_by_label.get(label, _("Unknown type"))
        return label

    def filters_active(self):
        """Check if any filters are active; returns true if form fields other than sort or q are set"""
        if self.is_valid():
            return bool(
                {
                    k: v
                    for k, v in self.cleaned_data.items()
                    if k not in ["q", "sort"] and bool(v)
                }
            )
        return False

    def set_choices_from_facets(self, facets):
        """Set choices on field from a dictionary of facets"""
        # borrowed from ppa-django;
        # populate facet field choices from current facets
        for key, facet_dict in facets.items():
            # restructure dict to set values of each key to tuples of (label, count)
            facet_dict = {
                label: (self.get_translated_label(key, label), count)
                for (label, count) in facet_dict.items()
            }
            # use field from facet fields map or else field name as is
            formfield = self.solr_facet_fields.get(key, key)
            # for each facet, set the corresponding choice field
            if formfield in self.fields:
                self.fields[formfield].populate_from_facets(facet_dict)

    def clean_q(self):
        """Clean keyword search query term; converts any typographic
        quotes to straight quotes"""
        query = self.cleaned_data.get("q")
        if query:
            return simplify_quotes(query)
        return query  # return since could be None or empty string

    def clean(self):
        """Validate form"""
        cleaned_data = super().clean()
        q = cleaned_data.get("q")
        sort = cleaned_data.get("sort")
        if sort == "relevance" and (not q or q == ""):
            # Translators: Error message when relevance sort is selected without a search query
            self.add_error(
                "q", _("Relevance sort is not available without a keyword search term.")
            )
        # additional validation for regex mode due to some queries that cause Lucene errors
        mode = cleaned_data.get("mode")
        if mode == "regex":
            # reused text about needing an escape character
            needs_escape = (
                lambda char: f"If you are searching for the character {char} in a transcription, escape it with \ by writing \{char} instead."
            )
            # see error messages for explanations of each regex here
            if re.search(r"((?<!\\)\{[^0-9])|(^\{)|((?<!\\)\{[^\}]*$)", q):
                print(q)
                self.add_error(
                    "q",
                    # Translators: error message for malformed curly brace in regular expression
                    _(
                        "Regular expression cannot contain { without a preceding character, without an integer afterwards, or without a closing }. %s"
                        % needs_escape("{")
                    ),
                )
            if re.search(r"(^\*)|((?<!\\)\*\*)", q):
                self.add_error(
                    "q",
                    # Translators: error message for malformed asterisk in regular expression
                    _(
                        "Regular expression cannot contain * without a preceding character, or multiple times in a row. %s"
                        % needs_escape("*")
                    ),
                )
            if re.search(r"(^\+)|((?<!\\)\+\+)", q):
                self.add_error(
                    "q",
                    # Translators: error message for malformed plus sign in regular expression
                    _(
                        "Regular expression cannot contain + without a preceding character, or multiple times in a row. %s"
                        % needs_escape("+")
                    ),
                )
            if re.search(r"(?<!\\)\<", q):
                self.add_error(
                    "q",
                    # Translators: error message for malformed less than sign in regular expression
                    _(
                        "Regular expression cannot contain < or use a negative lookbehind query. %s"
                        % needs_escape("<")
                    ),
                )
            if re.search(r"((?<!\\)\\[ABCE-RTUVXYZabce-rtuvxyz0-9])|((?<!\\)\\$)", q):
                # see https://github.com/apache/lucene/issues/11678 for more information
                self.add_error(
                    "q",
                    # Translators: error message for malformed backslash in regular expression
                    _(
                        "Regular expression cannot contain the escape character \\ followed by an alphanumeric character other than one of DdSsWw, or at the end of a query. %s"
                        % needs_escape("\\")
                    ),
                )


class DocumentChoiceField(forms.ModelChoiceField):
    """Add a summary of each document to a form (used for document merging)"""

    label_template = get_template("corpus/snippets/document_option_label.html")

    def label_from_instance(self, document):
        return self.label_template.render({"document": document})


class DocumentMergeForm(forms.Form):
    RATIONALE_CHOICES = [
        ("duplicate", "Duplicate"),
        ("join", "Join"),
        ("other", "Other (please specify)"),
    ]
    primary_document = DocumentChoiceField(
        label="Select primary document",
        queryset=None,
        help_text=(
            "Select the primary document, which will be used as the merged document PGPID. "
            "All other PGPIDs will be added to the list of old PGPIDs. "
            "All metadata, tags, footnotes, and log entries will be combined on the merged document."
        ),
        empty_label=None,
        widget=forms.RadioSelect,
    )
    rationale = forms.ChoiceField(
        widget=forms.RadioSelect,
        required=True,
        label="Rationale",
        help_text="Choose the option that best explains why these documents are being merged; will be included in the document history.",
        choices=RATIONALE_CHOICES,
    )
    rationale_notes = forms.CharField(
        required=False,
        label="Rationale notes",
        widget=forms.Textarea(),
    )

    def __init__(self, *args, **kwargs):
        document_ids = kwargs.get("document_ids", [])

        # Remove the added kwarg so that the super method doesn't error
        try:
            del kwargs["document_ids"]
        except KeyError:
            pass

        super().__init__(*args, **kwargs)
        self.fields["primary_document"].queryset = Document.objects.filter(
            id__in=document_ids
        )
        self.initial["rationale"] = "duplicate"

    def clean(self):
        cleaned_data = super().clean()
        rationale = cleaned_data.get("rationale")
        rationale_notes = cleaned_data.get("rationale_notes")

        if rationale == "other" and not rationale_notes:
            msg = 'Additional information is required when selecting "Other".'
            self.add_error("rationale", msg)


class TagChoiceField(forms.ModelChoiceField):
    """Add a count of tagged documents to a tag label on a form (used for tag merging)"""

    def label_from_instance(self, tag):
        return "%s (%s tagged)" % (tag.name, tag.item_count)


class TagMergeForm(forms.Form):
    primary_tag = TagChoiceField(
        label="Select primary tag",
        queryset=None,
        help_text=(
            "Select the primary tag, which will replace the names of the other selected tags. "
            "All items tagged with the other selected tags will then only be tagged with the primary tag."
        ),
        empty_label=None,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        tag_ids = kwargs.get("tag_ids", [])

        # Remove the added kwarg so that the super method doesn't error
        try:
            del kwargs["tag_ids"]
        except KeyError:
            pass

        super().__init__(*args, **kwargs)
        # get queryset and annotate with tagged document count
        self.fields["primary_tag"].queryset = Tag.objects.filter(
            id__in=tag_ids
        ).annotate(
            item_count=Count("taggit_taggeditem_items", distinct=True),
        )


class DocumentPersonForm(forms.ModelForm):
    class Meta:
        model = PersonDocumentRelation
        fields = (
            "person",
            "type",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "person": autocomplete.ModelSelect2(url="entities:person-autocomplete"),
            "type": autocomplete.ModelSelect2(),
        }


class DocumentPlaceForm(forms.ModelForm):
    class Meta:
        model = DocumentPlaceRelation
        fields = (
            "place",
            "type",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "place": autocomplete.ModelSelect2(url="entities:place-autocomplete"),
            "type": autocomplete.ModelSelect2(),
        }


class DocumentEventWidgetWrapper(RelatedFieldWidgetWrapper):
    """Override of RelatedFieldWidgetWrapper to insert custom url params into
    'add new object' link"""

    def get_context(self, name, value, attrs):
        """Override get_context to insert an additional URL param, from_document,
        in order to change min_num dynamically"""
        context = super().get_context(name, value, attrs)
        context["url_params"] += "&from_document=true"
        return context

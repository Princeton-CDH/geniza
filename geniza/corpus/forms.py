from django import forms
from django.template.loader import get_template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from geniza.common.fields import RangeField, RangeForm, RangeWidget
from geniza.common.utils import simplify_quotes
from geniza.corpus.models import Document


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


class RadioSelectWithDisabled(SelectDisabledMixin, forms.RadioSelect):
    """
    Subclass of :class:`django.forms.RadioSelect` with option to mark
    a choice as disabled.
    """


class CheckboxSelectWithCount(forms.CheckboxSelectMultiple):
    # extend default CheckboxSelectMultiple to add facet counts and
    # include per-item count as a data attribute
    facet_counts = {}

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        for optgroup in context["widget"].get("optgroups", []):
            for option in optgroup[1]:
                count = self.facet_counts.get(option["value"], None)
                # make facet count available as data-count attribute
                if count:
                    option["attrs"]["data-count"] = f"{count:,}"
        return context


class FacetFieldMixin:
    # Borrowed from ppa-django / mep-django
    # - turn off choice validation (shouldn't fail if facets don't get loaded)
    # - default is not required

    def __init__(self, *args, **kwargs):
        if "required" not in kwargs:
            kwargs["required"] = False

        # get custom kwarg and remove before passing to MultipleChoiceField
        # super method, which would cause an error
        self.widget.legend = None
        if "legend" in kwargs:
            self.widget.legend = kwargs["legend"]
            del kwargs["legend"]

        super().__init__(*args, **kwargs)

        # if no custom legend, set it from label
        if not self.widget.legend:
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
            (val, mark_safe(f'<span>{val}</span><span class="count">{count:,}</span>'))
            for val, count in facet_dict.items()
        )
        # pass the counts to the widget so it can be set as a data attribute
        self.widget.facet_counts = facet_dict


class CheckboxInputWithCount(forms.CheckboxInput):
    # extend default CheckboxInput to add facet count as a data attribute
    facet_counts = {}

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        count = self.facet_counts.get("true", None)
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
        count = facet_dict.get("true", 0)
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
                "placeholder": _("search by keyword"),
                # Translators: accessible label for keyword search input
                "aria-label": _("Keyword or Phrase"),
                "type": "search",
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

    # NOTE these are not set by default!
    error_css_class = "error"
    required_css_class = "required"

    sort = forms.ChoiceField(
        # Translators: label for form sort field
        label=_("Sort by"),
        choices=[
            (choice[0], mark_safe(f"<span>{choice[1]}</span>"))
            for choice in SORT_CHOICES
        ],
        required=False,
        widget=RadioSelectWithDisabled,
    )
    # Translators: label for filter documents by date range
    docdate = RangeField(
        label=_("Document Dates (CE)"),
        required=False,
        widget=YearRangeWidget(
            attrs={"size": 4, "data-action": "input->search#update"},
        ),
    )

    doctype = FacetChoiceField(
        # Translators: label for document type search form filter
        label=_("Document Type"),
    )
    has_image = BooleanFacetField(
        # Translators: label for "has image" search form filter
        label=_("Has Image"),
    )
    has_transcription = BooleanFacetField(
        # Translators: label for "has transcription" search form filter
        label=_("Has Transcription"),
    )
    has_translation = BooleanFacetField(
        # Translators: label for "has translation" search form filter
        label=_("Has Translation"),
    )
    has_discussion = BooleanFacetField(
        # Translators: label for "has discussion" search form filter
        label=_("Has Discussion"),
    )

    # mapping of solr facet fields to form input
    solr_facet_fields = {
        "type": "doctype",
        "has_digital_edition": "has_transcription",
        "has_translation": "has_translation",
        "has_discussion": "has_discussion",
    }

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
            # use field from facet fields map or else field name as is
            formfield = self.solr_facet_fields.get(key, key)
            # for each facet, set the corresponding choice field
            if formfield in self.fields:
                self.fields[formfield].populate_from_facets(facet_dict)

    def clean_q(self):
        query = self.cleaned_data.get("q")
        if query:
            return simplify_quotes(query)
        return query

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

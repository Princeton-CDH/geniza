from django import forms
from django.forms import renderers
from django.template.loader import get_template
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

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


class FacetChoiceField(forms.ChoiceField):
    """Choice field where choices are set based on Solr facets"""

    # Borrowed from ppa-django / mep-django
    # - turn off choice validation (shouldn't fail if facets don't get loaded)
    # - default is not required

    # use a custom widget so we can add facet count as a data attribute
    widget = CheckboxSelectWithCount

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


class DocumentSearchForm(forms.Form):

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
        # ("input_date", "Input Date (Latest – Earliest)"),
        # Translators: label for descending sort by number of scholarship records
        ("scholarship_desc", _("Scholarship Records (Most–Least)")),
        # Translators: label for ascending sort by number of scholarship records
        ("scholarship_asc", _("Scholarship Records (Least–Most)")),
    ]

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

    doctype = FacetChoiceField(
        # Translators: label for document type search form filter
        label=_("Document Type"),
    )

    # mapping of solr facet fields to form input
    solr_facet_fields = {"type": "doctype"}

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

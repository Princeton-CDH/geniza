from django import forms
from django.utils.translation import gettext as _


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
        choices=SORT_CHOICES,
        required=False,
        widget=SelectWithDisabled,
    )

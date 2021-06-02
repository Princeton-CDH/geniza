from django import forms


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
    query = forms.CharField(
        label="Keyword or Phrase",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "search by keyword",
                "aria-label": "Keyword or Phrase",
                "type": "search",
            }
        ),
    )

    # sort still TODO; single choice only for display, for now
    SORT_CHOICES = [
        ("relevance", "Relevance"),
        # ("input_date", "Input Date (Latest – Earliest)"),
    ]

    # NOTE these are not set by default!
    error_css_class = "error"
    required_css_class = "required"

    sort = forms.ChoiceField(
        label="Sort by", choices=SORT_CHOICES, required=False, widget=SelectWithDisabled
    )

    def __init__(self, data=None, *args, **kwargs):
        """
        Override to set choices dynamically based on form kwargs.
        """
        super().__init__(data=data, *args, **kwargs)

        # if a keyword search term is not present, relevance sort is disabled
        if not data or not data.get("query", None):
            self.fields["sort"].widget.choices[0] = (
                self.SORT_CHOICES[0][0],
                {"label": self.SORT_CHOICES[0][1], "disabled": True},
            )

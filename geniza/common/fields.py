from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from natsort import natsort_keygen, ns


class NaturalSortField(models.CharField):
    """Natural sort field for Django models.  Takes a field name, and uses
    :mod:`natsort` to generate a natural sort value based on the value of that field."""

    # inspired by / adapted from https://github.com/nathforge/django-naturalsortfield

    def __init__(self, for_field, **kwargs):
        self.for_field = for_field
        kwargs.setdefault("db_index", True)
        kwargs.setdefault("editable", False)
        kwargs.setdefault("max_length", 255)
        # treat numbers as integers, ignore case, treat +/- as strings
        self.natsort_key = natsort_keygen(alg=ns.INT | ns.IGNORECASE | ns.UNSIGNED)
        super().__init__(**kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["for_field"] = self.for_field
        return name, path, args, kwargs

    def pre_save(self, model_instance, add):
        """Set the value of the field from `for_field` value before it is saved. Generates a string
        based on the output of :meth:`natsort.natsort_key`."""
        # natsort_key returns a tuple; format and combine into a string for storage
        return "".join(
            [
                self.format_val(k)
                for k in self.natsort_key(getattr(model_instance, self.for_field))
            ]
        )

    def format_val(self, val):
        """Format values that can occur in a natural sort key tuple."""
        # format numbers with leading zeros
        if isinstance(val, int):
            return f"{val:06}"  # 6 digits, leading zeros
        # no adjustment needed for strings
        return val


# RangeWidget and RangeField adapted  mep-django


class RangeWidget(forms.MultiWidget):
    """date range widget, for two numeric inputs"""

    #: template to use to render range multiwidget
    # (based on multiwidget, but adds "to" between dates)
    template_name = "common/widgets/rangewidget.html"

    def __init__(self, *args, **kwargs):
        widgets = [
            forms.NumberInput(attrs={"aria-label": "start"}),
            forms.NumberInput(attrs={"aria-label": "end"}),
        ]
        super().__init__(widgets, *args, **kwargs)

    def decompress(self, value):
        if value:
            return [int(val) if val else None for val in value]
        return [None, None]


class RangeField(forms.MultiValueField):
    """Date range field, for two numeric inputs. Compresses to a tuple of
    two values for the start and end of the range; tuple values set to
    None for no input."""

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
        """Compress into a single value; returns a two-tuple of range end,
        start."""

        # If neither values is set, return None
        if not any(data_list):
            return None

        # if both values are set and the first is greater than the second,
        # raise a validation error
        if all(data_list) and len(data_list) == 2 and data_list[0] > data_list[1]:
            raise ValidationError(
                "Invalid range (%s - %s)" % (data_list[0], data_list[1])
            )

        return (data_list[0], data_list[1])

    def set_min_max(self, min_val, max_val):
        """Set a min and max value for :class:`RangeWidget` attributes
        and placeholders.

        :param min_value: minimum value to set on widget
        :type min_value: int
        :param max_value: maximum value to set on widget
        :type max_value: int
        :rtype: None
        """
        start_widget, end_widget = self.widget.widgets
        # set placeholders for widgets individually
        start_widget.attrs["placeholder"] = min_val
        end_widget.attrs["placeholder"] = max_val
        # valid min and max for both via multiwidget
        self.widget.attrs.update({"min": min_val, "max": max_val})


class RangeForm(forms.Form):
    """Form mixin to initialize min/max values for range fields."""

    def set_range_minmax(self, range_minmax):
        """Set the min, max, and placeholder values for all
        :class:`~mep.common.forms.RangeField` instances.

        :param range_minmax: a dictionary with form fields as key names and
            tuples of min and max integers as values.
        :type range_minmax: dict

        :rtype: None
        """
        for field_name, min_max in range_minmax.items():
            self.fields[field_name].set_min_max(min_max[0], min_max[1])

    def __init__(self, data=None, *args, **kwargs):
        """
        Override to set choices dynamically and configure min-max range values
        based on form kwargs.
        """
        # pop range_minmax out of kwargs to avoid clashing
        # with django args
        range_minmax = kwargs.pop("range_minmax", {})

        super().__init__(data=data, *args, **kwargs)

        # call function to set min_max and placeholders
        self.set_range_minmax(range_minmax)

from django.db import models
from natsort import natsort_key


class NaturalSortField(models.CharField):
    """Natural sort field for Django models.  Takes a field name, and uses
    :mod:`natsort` to generate a natural sort value based on the value of that field."""

    # inspired by / adapted from https://github.com/nathforge/django-naturalsortfield

    def __init__(self, for_field, **kwargs):
        self.for_field = for_field
        kwargs.setdefault("db_index", True)
        kwargs.setdefault("editable", False)
        kwargs.setdefault("max_length", 255)
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
                for k in natsort_key(getattr(model_instance, self.for_field))
            ]
        )

    def format_val(self, val):
        """Format values that can occur in a natural sort key tuple."""
        # format numbers with leading zeros
        if isinstance(val, int):
            return f"{val:06}"  # 6 digits, leading zeros
        # no adjustment needed for strings
        return val

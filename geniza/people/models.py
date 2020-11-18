from django.db import models
from django.utils.translation import gettext_lazy as _


class Person(models.Model):
    """Person mentioned in or related to a geniza document."""
    name = models.CharField(max_length=100, help_text=_("Full name"))
    profession = models.ForeignKey("Profession", on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("person")
        verbose_name_plural = _("people")


class Profession(models.Model):
    """Historical profession held by a person mentioned in the geniza."""
    title = models.CharField(max_length=100)

    class Meta:
        verbose_name = _("profession")
        verbose_name_plural = _("professions")

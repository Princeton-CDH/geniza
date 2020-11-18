from django.db import models
from django.utils.translation import gettext_lazy as _


class Person(models.Model):
    """Person mentioned in or related to a geniza document."""
    name = models.CharField(max_length=100)
    profession = models.ForeignKey("Profession", null=True, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("-name",)
        verbose_name_plural = "people"


class Profession(models.Model):
    """Historical profession held by a person mentioned in the geniza."""
    title = models.CharField(max_length=100)
    description = models.TextField(null=True)

    def __str__(self) -> str:
        return f"{self.title} ({self.description})"

    class Meta:
        ordering = ("-title",)

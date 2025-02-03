from functools import cache

from django.contrib.auth.models import User
from django.db import models
from django.db.models.functions.text import Lower
from django.utils.safestring import mark_safe
from modeltranslation.utils import fallbacks


def cached_class_property(f):
    """
    Reusable decorator to cache a class property, as opposed to an instance property.
    from https://stackoverflow.com/a/71887897
    """
    return classmethod(property(cache(f)))


# Create your models here.
class TrackChangesModel(models.Model):
    """:class:`~django.models.Model` mixin that keeps a copy of initial
    data in order to check if fields have been changed. Change detection
    only works on the current instance of an object."""

    # NOTE: copied from ppa-django codebase

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # store a copy of model data to allow for checking if
        # it has changed
        self.__initial = self.__dict__.copy()

    def save(self, *args, **kwargs):
        """Saves data and reset copy of initial data."""
        super().save(*args, **kwargs)
        # update copy of initial data to reflect saved state
        self.__initial = self.__dict__.copy()

    def has_changed(self, field):
        """check if a field has been changed"""
        return getattr(self, field) != self.__initial[field]

    def initial_value(self, field):
        """return the initial value for a field"""
        return self.__initial[field]


class UserProfile(models.Model):
    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)
    github_coauthor = models.CharField(
        "GitHub Co-Author Email",
        help_text=mark_safe(
            """Co-author information to credit your contributions
        in GitHub Backups.
        See <a href='https://docs.github.com/en/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/creating-a-commit-with-multiple-authors'>GitHub documentation</a>
        for instructions on finding or setting yours."""
        ),
        blank=True,
        max_length=255,
    )
    # ref by string to avoid circular import with track changes model
    creator = models.OneToOneField(
        "footnotes.Creator",
        null=True,
        blank=True,
        help_text="Author record for scholarship records, for users who are also authors",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        # needed for display label in admin
        return "User profile for %s" % (self.user)


class DisplayLabelMixin:
    """
    Mixin for models with translatable display labels that may differ from names, in
    order to override fallback behavior when a label for the current language is not defined.
    Used for search response handling and display on the public frontend.

    Example: DocumentType with name 'Legal' has a display label in English, 'Legal document'.
    In Hebrew, it only has a name 'מסמך משפטי' and no display label. In English, we want to show
    DocumentType.display_label_en. In Hebrew, we want to show DocumentType.name_he because
    display_label_he is not defined. We also need to ensure that the document type
    מסמך משפטי can be looked up by display_label_en, as that is what gets indexed in solr.
    """

    def __str__(self):
        # temporarily turn off model translate fallbacks;
        # if display label for current language is not defined,
        # we want name for the current language rather than the
        # fallback value for display label
        with fallbacks(False):
            current_lang_label = self.display_label or self.name

        return current_lang_label or self.display_label or self.name

    def natural_key(self):
        """Natural key, name"""
        return (self.name,)

    @classmethod
    def objects_by_label(cls):
        """A dict of object instances keyed on English display label, used for search form
        and search results, which should be based on Solr facet and query responses (indexed in
        English)."""
        return {
            # lookup on display_label_en/name_en since solr should always index in English
            (obj.display_label_en or obj.name_en): obj
            for obj in cls.objects.all()
        }


class TaggableMixin:
    """Mixin for taggable models with convenience functions for generating lists of tags"""

    def all_tags(self):
        """comma delimited string of all tags for this instance"""
        return ", ".join(t.name for t in self.tags.all())

    all_tags.short_description = "tags"

    def alphabetized_tags(self):
        """tags in alphabetical order, case-insensitive sorting"""
        return self.tags.order_by(Lower("name"))

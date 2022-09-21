from django.contrib.auth.models import User
from django.db import models
from django.utils.safestring import mark_safe


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

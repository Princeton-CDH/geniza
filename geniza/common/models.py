from django.db import models

# Create your models here.
class TrackChangesModel(models.Model):
    ''':class:`~django.models.Model` mixin that keeps a copy of initial
    data in order to check if fields have been changed. Change detection
    only works on the current instance of an object.'''

    # NOTE: copied from ppa-django codebase

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # store a copy of model data to allow for checking if
        # it has changed
        self.__initial = self.__dict__.copy()

    def save(self, *args, **kwargs):
        '''Saves data and reset copy of initial data.'''
        super().save(*args, **kwargs)
        # update copy of initial data to reflect saved state
        self.__initial = self.__dict__.copy()

    def has_changed(self, field):
        '''check if a field has been changed'''
        return getattr(self, field) != self.__initial[field]

    def initial_value(self, field):
        '''return the initial value for a field'''
        return self.__initial[field]
from django.db import models


class Library(models.Model):
    '''Library or archive that holds Geniza fragments'''
    name = models.CharField(max_length=255)
    abbrev = models.CharField('Abbreviation', max_length=255)
    url = models.URLField('URL', blank=True)

    class Meta:
        verbose_name_plural = 'Libraries'

    def __str__(self):
        return self.name

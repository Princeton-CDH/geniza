from django.db import models

class Person(models.Model):
    # both first and last name are optional, just stubbing for now
    sort_name = models.CharField(max_length=255,
        help_text='Input the name as it should be sorted. (e.g. "Mercury, Freddie")')

    def __str__(self):
        return self.sort_name

    class Meta:
        verbose_name_plural = 'people'
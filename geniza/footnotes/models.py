from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from multiselectfield import MultiSelectField
# https://pypi.org/project/django-multiselectfield/
from sortedm2m.fields import SortedManyToManyField
# https://github.com/jazzband/django-sortedm2m

class SourceType(models.Model):
    type = models.CharField(max_length=255)

    def __str__(self):
        return self.type


class Creator(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.last_name}, {self.first_name}'

    class Meta:
        ordering = ['last_name']

class Source(models.Model):
    authors = SortedManyToManyField(Creator)
    title = models.CharField(max_length=255)
    year = models.PositiveIntegerField(blank=True, null=True)
    edition = models.CharField(max_length=255, blank=True)
    volume = models.CharField(max_length=255, blank=True)
    page_range = models.CharField(max_length=255, blank=True,
        help_text='The range of pages being cited. Do not include "p", "pg", etc. and follow the format # or #-#')
    source_type = models.ForeignKey(SourceType, on_delete=models.CASCADE)
    language = models.ForeignKey('corpus.LanguageScript', on_delete=models.SET_NULL,
        help_text='In what language was the source published?', null=True)

    # class Meta:
    #     ordering = ['all_authors']

    def __str__(self):
        return self.all_authors + '. ' + f'"{self.title}"'

    @property
    def all_authors(self):
        return '; '.join([str(author) for author in self.authors.all()])


class Footnote(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE)

    page_range = models.CharField(max_length=255, blank=True,
        help_text='The range of pages being cited. Do not include "p", "pg", etc. and follow the format # or #-#')

    EDITION = 'E'
    TRANSLATION = 'T'
    DISCUSSION = 'D'
    DOCUMENT_RELATION_TYPES = (
        (EDITION, 'Edition'),
        (TRANSLATION, 'Translation'),
        (DISCUSSION, 'Discussion')
    )
    
    document_relation_types = MultiSelectField(choices=DOCUMENT_RELATION_TYPES,
        help_text='How does the document relate to a source?')
    notes = models.TextField(blank=True)

    # Generic relationship
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    def __str__(self):
        return str(self.source)


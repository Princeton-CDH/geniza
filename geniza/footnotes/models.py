from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from multiselectfield import MultiSelectField


class SourceType(models.Model):
    '''type of source'''
    type = models.CharField(max_length=255)

    def __str__(self):
        return self.type


class SourceLanguage(models.Model):
    '''language of a source document'''
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=10, help_text='ISO language code')

    def __str__(self):
        return self.name


class Creator(models.Model):
    '''author or other contributor to a source'''
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.last_name}, {self.first_name}'

    class Meta:
        ordering = ['last_name', 'first_name']
        constraints = [
            models.UniqueConstraint(fields=['first_name', 'last_name'],
                                    name='creator_unique_name')
        ]


class Authorship(models.Model):
    """Ordered relationship between :class:`Creator` and :class:`Source`."""
    creator = models.ForeignKey(Creator, on_delete=models.CASCADE)
    source = models.ForeignKey('Source', on_delete=models.CASCADE)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('sort_order',)

    def __str__(self) -> str:
        return '%s %d on "%s"' % (self.creator, self.sort_order,
                                  self.source.title)


class Source(models.Model):
    '''a published or unpublished work related to geniza materials'''
    creators = models.ManyToManyField(Creator, through=Authorship)
    title = models.CharField(max_length=255)
    year = models.PositiveIntegerField(blank=True, null=True)
    edition = models.CharField(max_length=255, blank=True)
    volume = models.CharField(max_length=255, blank=True)
    page_range = models.CharField(
        max_length=255, blank=True,
        help_text='The range of pages being cited. Do not include ' +
                  '"p", "pg", etc. and follow the format # or #-#')
    source_type = models.ForeignKey(SourceType, on_delete=models.CASCADE)
    languages = models.ManyToManyField(
        SourceLanguage,
        help_text='The language(s) the source is written in')

    class Meta:
        # set default order to title, year for now since first-author order
        # requires queryset annotation
        ordering = ['title', 'year']

    def __str__(self):
        return self.all_creators() + '. ' + f'"{self.title}"'

    def all_creators(self):
        return '; '.join([str(c.creator) for c in self.authorship_set.all()])
    all_creators.short_description = 'Creators'
    all_creators.admin_order_field = 'first_author'  # set in admin queryset


class Footnote(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE)

    page_range = models.CharField(
        max_length=255, blank=True,
        help_text='The range of pages being cited. Do not include "p", ' +
                  '"pg", etc. and follow the format # or #-#')

    EDITION = 'E'
    TRANSLATION = 'T'
    DISCUSSION = 'D'
    DOCUMENT_RELATION_TYPES = (
        (EDITION, 'Edition'),
        (TRANSLATION, 'Translation'),
        (DISCUSSION, 'Discussion')
    )

    doc_relation = MultiSelectField(
        'Document relation',
        choices=DOCUMENT_RELATION_TYPES,
        help_text='How does the source relate to this document?')
    notes = models.TextField(blank=True)

    # Generic relationship
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    def __str__(self):
        return str(self.source)

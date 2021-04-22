from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.humanize.templatetags.humanize import ordinal
from django.contrib.postgres.fields import JSONField

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


class CollectionManager(models.Manager):

    def get_by_natural_key(self, last_name, first_name):
        return self.get(last_name=last_name, first_name=first_name)


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

    def natural_key(self):
        return (self.last_name, self.first_name)


class Authorship(models.Model):
    """Ordered relationship between :class:`Creator` and :class:`Source`."""
    creator = models.ForeignKey(Creator, on_delete=models.CASCADE)
    source = models.ForeignKey('Source', on_delete=models.CASCADE)
    sort_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ('sort_order',)

    def __str__(self) -> str:
        return '%s, %s author on "%s"' % \
            (self.creator, ordinal(self.sort_order), self.source.title)


class Source(models.Model):
    '''a published or unpublished work related to geniza materials'''
    authors = models.ManyToManyField(Creator, through=Authorship)
    title = models.CharField(max_length=255, blank=True)
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
    url = models.URLField(blank=True)
    # preliminary place to store transcription text; should not be editable
    notes = models.TextField(blank=True)

    class Meta:
        # set default order to title, year for now since first-author order
        # requires queryset annotation
        ordering = ['title', 'year']

    def __str__(self):
        # generate simple string representation similar to
        # how records were listed in the metadata spreadsheet
        # author lastname, title (year)

        # author
        # author, title
        # author, title (year)
        # author (year)

        text = ''
        if self.authorship_set.exists():
            author_lastnames = [a.creator.last_name
                                for a in self.authorship_set.all()]
            # combine the last pair with and; combine all others with comma
            # thanks to https://stackoverflow.com/a/30084022
            if len(author_lastnames) > 1:
                text = " and ".join([", ".join(author_lastnames[:-1]),
                                     author_lastnames[-1]])
            else:
                text = author_lastnames[0]

        if self.title:
            # delimit with comma if there is an author
            if text:
                text = ', '.join([text, self.title])
            else:
                text = self.title

        if self.year:
            text = '%s (%d)' % (text, self.year)
        return text

    def all_authors(self):
        '''semi-colon delimited list of authors in order'''
        return '; '.join([str(c.creator) for c in self.authorship_set.all()])
    all_authors.short_description = 'Authors'
    all_authors.admin_order_field = 'first_author'  # set in admin queryset


class Footnote(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    location = models.CharField(
        max_length=255, blank=True,
        help_text='Location within the source ' +
                  '(e.g., document number or page range)')

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
    content = models.JSONField(
        blank=True, null=True,
        help_text='Transcription content (preliminary)')

    # Generic relationship
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    def __str__(self):
        return 'Footnote on %s (%s)' % \
            (self.content_object, self.source)

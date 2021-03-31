from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from multiselectfield import MultiSelectField
# https://pypi.org/project/django-multiselectfield/

from geniza.people.models import Person
from geniza.corpus.models import LanguageScript

class SourceType(models.Model):
    type = models.CharField(max_length=255)

    def __str__(self):
        return self.type


class Source(models.Model):
    # TODO: Multiple authors
    author = models.ForeignKey(Person, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    year = models.PositiveIntegerField(blank=True, null=True)
    # TODO: `edition_number` isn't a number. Can we call it `edition` ?
    edition_number = models.CharField(max_length=255, blank=True)
    # TODO: What kind of values would volume contain? Would they just be an int?
    volume = models.CharField(max_length=255, blank=True)
    page_range = models.CharField(max_length=255, blank=True,
        help_text='The range of pages being cited. Do not include "p", "pg", etc. and follow the format # or #-#')
    source_type = models.ForeignKey(SourceType, on_delete=models.CASCADE)
    # TODO: (RR) Null? 
    # TODO: (RR) Should there be a default language?
    language = models.ForeignKey(LanguageScript, on_delete=models.SET_NULL,
        help_text='In what language was the source published?', null=True)

    class Meta:
        ordering = ['author__last_name']

    def __str__(self):
        # TODO: Generate citation
        return self.title


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
    # TODO: Confirm default=EDITION is ok. As a required field this needs to 
    #  have a default value.
    document_relation_types = MultiSelectField(choices=DOCUMENT_RELATION_TYPES,  default=EDITION,
        help_text='How does the document relate to a source?')
    notes = models.TextField(blank=True)

    # Generic relationship
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    def __str__(self):
        # TODO: Generate citation
        return str(self.source)

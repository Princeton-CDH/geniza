from django.db import models

from multiselectfield import MultiSelectField
# https://pypi.org/project/django-multiselectfield/

from geniza.people.models import Person
from geniza.corpus.models import LanguageScript

class SourceType(models.Model):
    type = models.CharField(max_length=255)

    def __str__(self):
        return self.type


class Source(models.Model):
    # TODO: Confirm that "delete all footnotes when person is deleted"
    #  is the expected behavior
    author = models.ForeignKey(Person, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    # TODO: Presumably they'll want just month and year? Should we handle that?
    publish_date = models.DateField(blank=True, null=True)
    edition_number = models.CharField(max_length=255, blank=True)
    # TODO: What kind of values would volume contain? Would they just be an int?
    volume = models.CharField(max_length=255, blank=True)
    # TODO: Should this formatting be enforced by the `clean` method? or is the 
    #  help text sufficient?
    page_range = models.CharField(max_length=255, blank=True,
        help_text='The range of pages being cited. Please do not include "p", "pg", etc. and follow the format # or #-#')
    # TODO: Is cascade appropriate? We want this field to be required.
    source_type = models.ForeignKey(SourceType, on_delete=models.SET_NULL, null=True)
    # TODO: Should there be a default language?
    language = models.ForeignKey(LanguageScript, on_delete=models.SET_NULL,
        help_text='In what language was the source published?', null=True)

    EDITION = 'E'
    TRANSLATION = 'T'
    DISCUSSION = 'D'
    DOCUMENT_RELATIONS = (
        (EDITION, 'Edition'),
        (TRANSLATION, 'Translation'),
        (DISCUSSION, 'Discussion')
    )
    # TODO: Confirm default=EDITION is ok. As a required field this needs to 
    #  have a default value.
    # TODO: `document_relation_types` ?
    document_relations = MultiSelectField(choices=DOCUMENT_RELATIONS,  default=EDITION,
        help_text='How does the document relate to a source?')

    class Meta:
        ordering = ['author__last_name']


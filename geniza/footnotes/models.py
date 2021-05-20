from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.humanize.templatetags.humanize import ordinal
from gfklookupwidget.fields import GfkLookupField

from modeltranslation.manager import MultilingualManager
from multiselectfield import MultiSelectField


class SourceType(models.Model):
    """type of source"""

    type = models.CharField(max_length=255)

    def __str__(self):
        return self.type


class SourceLanguage(models.Model):
    """language of a source document"""

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=10, help_text="ISO language code")

    def __str__(self):
        return self.name


class CreatorManager(MultilingualManager):
    def get_by_natural_key(self, last_name, first_name):
        return self.get(last_name=last_name, first_name=first_name)


class Creator(models.Model):
    """author or other contributor to a source"""

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    objects = CreatorManager()

    def __str__(self):
        return ", ".join([n for n in [self.last_name, self.first_name] if n])

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["first_name", "last_name"], name="creator_unique_name"
            )
        ]

    def natural_key(self):
        return (self.last_name, self.first_name)


class Authorship(models.Model):
    """Ordered relationship between :class:`Creator` and :class:`Source`."""

    creator = models.ForeignKey(Creator, on_delete=models.CASCADE)
    source = models.ForeignKey("Source", on_delete=models.CASCADE)
    sort_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ("sort_order",)

    def __str__(self) -> str:
        return '%s, %s author on "%s"' % (
            self.creator,
            ordinal(self.sort_order),
            self.source.title,
        )


class Source(models.Model):
    """a published or unpublished work related to geniza materials"""

    authors = models.ManyToManyField(Creator, through=Authorship)
    title = models.CharField(max_length=255, blank=True, null=True)
    year = models.PositiveIntegerField(blank=True, null=True)
    edition = models.CharField(max_length=255, blank=True)
    volume = models.CharField(
        max_length=255,
        blank=True,
        help_text="Volume of a multivolume book, or journal volume for an article",
    )
    journal = models.CharField(
        max_length=255, blank=True, help_text="Title of the journal, for an article"
    )
    page_range = models.CharField(
        max_length=255,
        blank=True,
        help_text="The range of pages being cited. Do not include "
        + '"p", "pg", etc. and follow the format # or #-#',
    )
    other_info = models.TextField(
        blank=True, help_text="Additional citation information, if any"
    )
    source_type = models.ForeignKey(SourceType, on_delete=models.CASCADE)
    languages = models.ManyToManyField(
        SourceLanguage, help_text="The language(s) the source is written in"
    )
    url = models.URLField(blank=True, max_length=300)
    # preliminary place to store transcription text; should not be editable
    notes = models.TextField(blank=True)

    class Meta:
        # set default order to title, year for now since first-author order
        # requires queryset annotation
        ordering = ["title", "year"]

    def __str__(self):
        # generate simple string representation similar to
        # how records were listed in the metadata spreadsheet
        # author lastname, title (year)

        # author
        # author, title
        # author, title (year)
        # author (year)
        # author, "title" journal vol (year)

        author = ""
        if self.authorship_set.exists():
            author_lastnames = [a.creator.last_name for a in self.authorship_set.all()]
            # combine the last pair with and; combine all others with comma
            # thanks to https://stackoverflow.com/a/30084022
            if len(author_lastnames) > 1:
                author = " and ".join(
                    [", ".join(author_lastnames[:-1]), author_lastnames[-1]]
                )
            else:
                author = author_lastnames[0]

        parts = []

        if self.title:
            # if this is an article, wrap title in quotes
            if self.source_type.type == "Article":
                parts.append('"%s"' % self.title)
            else:
                parts.append(self.title)

        if self.journal:
            parts.append(self.journal)
        if self.volume:
            parts.append(self.volume)
        if self.year:
            parts.append("(%d)" % self.year)

        # title, journal, etc should be joined by spaces only
        ref = " ".join(parts)

        # delimit with comma whichever values are set
        return ", ".join([val for val in (author, ref) if val])

    def all_authors(self):
        """semi-colon delimited list of authors in order"""
        return "; ".join([str(c.creator) for c in self.authorship_set.all()])

    all_authors.short_description = "Authors"
    all_authors.admin_order_field = "first_author"  # set in admin queryset


class Footnote(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Location within the source "
        + "(e.g., document number or page range)",
    )

    EDITION = "E"
    TRANSLATION = "T"
    DISCUSSION = "D"
    DOCUMENT_RELATION_TYPES = (
        (EDITION, "Edition"),
        (TRANSLATION, "Translation"),
        (DISCUSSION, "Discussion"),
    )

    doc_relation = MultiSelectField(
        "Document relation",
        choices=DOCUMENT_RELATION_TYPES,
        help_text="How does the source relate to this document?",
    )
    notes = models.TextField(blank=True)
    content = models.JSONField(
        blank=True, null=True, help_text="Transcription content (preliminary)"
    )
    url = models.URLField(
        blank=True, max_length=300, help_text="Link to the source (optional)"
    )

    # Generic relationship
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="corpus"),
    )
    object_id = GfkLookupField("content_type")
    content_object = GenericForeignKey()

    class Meta:
        ordering = ["source", "location"]

    def __str__(self):
        choices = dict(self.DOCUMENT_RELATION_TYPES)
        rel = " and ".join([choices[c] for c in self.doc_relation]) or "Footnote"
        return f"{rel} of {self.content_object}"

    def has_transcription(self):
        """Admin display field indicating presence of digitized transcription."""
        return bool(self.content)

    def display(self):
        # TODO: Should source be a required field?
        # source, location. notes
        # source. notes
        # source, location.
        return_str = str(self.source)
        if self.location:
            return_str += f", {self.location}"
        return_str += "."
        if self.notes:
            return_str += f" {self.notes}"
        return return_str

    has_transcription.short_description = "Digitized Transcription"
    has_transcription.boolean = True
    has_transcription.admin_order_field = "content"

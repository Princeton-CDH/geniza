from django.apps import apps  # used to dynamically get the Model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.humanize.templatetags.humanize import ordinal
from django.db import models
from django.utils.translation import gettext_lazy as _
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

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["first_name", "last_name"], name="creator_unique_name"
            )
        ]

    def __str__(self):
        return ", ".join([n for n in [self.last_name, self.first_name] if n])

    def natural_key(self):
        return (self.last_name, self.first_name)

    def firstname_lastname(self):
        """Creator full name, with first name first"""
        return " ".join([n for n in [self.first_name, self.last_name] if n])


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
        "Journal / Book",
        max_length=255,
        blank=True,
        help_text="Journal title (for an article) or book title (for a book section)",
    )
    page_range = models.CharField(
        max_length=255, blank=True, help_text="Page range for article or book section."
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
        parts = []
        author = ""
        if self.authorship_set.exists():
            author_lastnames = [
                a.creator.firstname_lastname() for a in self.authorship_set.all()
            ]
            # combine the last pair with and; combine all others with comma
            # thanks to https://stackoverflow.com/a/30084022
            if len(author_lastnames) > 1:
                author = " and ".join(
                    [", ".join(author_lastnames[:-1]), author_lastnames[-1]]
                )
            else:
                author = author_lastnames[0]

        if self.title:
            # if this is an article, wrap title in quotes
            if self.source_type.type == "Article":
                parts.append('"%s"' % self.title)
            else:
                parts.append(self.title)

        if self.languages:
            if not self.languages.all():
                languages = None
            else:
                # Separate languages with commas
                languages = ", ".join([l.name for l in self.languages.all()])

        # Source formatting for given source type

        if self.source_type.type == "Article":
            # S. D. Goitein, "Jewish Women in the Middle Ages" (English), Hadassah Magazine 55.2 (1973)
            citation = ""
            if author:
                citation += author
            if self.title:
                citation += ", " + self.title
            if languages:
                citation += " (" + languages + ")"
            if self.journal:
                citation += " " + self.journal
            if self.volume:
                citation += " " + self.volume
            if self.year:
                citation += " (" + str(self.year) + ")"
            if self.page_range:
                citation += " " + self.page_range
            return citation

        if self.source_type.type == "Book":
            # Moshe Gil, Palestine during the First Muslim Period, 634–1099, in Hebrew (Tel Aviv, 1983), vol. 2, doc. 134"""
            return f'{author}, {self.title} {"in "+languages+")" if languages else ""}, {self.volume if self.volume else ""} {"("+str(self.year)+")" if self.year else ""}{": "+str(self.page_range) if self.page_range else ""}'

        if self.source_type.type == "Book Section":
            # S. D. Goitein, "New Documents on the Gaonate in Palestine," in Salo Baron Jubilee Volume on the Occasion of His Seventy-fifth Birthday, ed. Arthur Hyman (New York, 1975), 2:55–74
            # TODO need field for place of publication
            return f'{author}, "{self.title}," {"in "+self.journal if self.journal else ""} {"("+str(self.year)+")," if self.year else ""}{" "+self.volume+": " if self.volume else ""}{str(self.page_range) if self.page_range else ""}'

            # TODO: formatted version with italics for book/journal title.
            # AJ (10/18/21) Added <i> but will require |safe in templates, will appear as html in admin, is this the right solution?

        # is Blog
        # Source objects exist with type Blog, but no formatting is given in #252

        if self.source_type.type == "Dissertation":
            # Ṣabīḥ ʿAodeh, "Eleventh Century Arabic Letters of Jewish Merchants from the Cairo Geniza" (PhD diss. Tel Aviv University, 1992), ??? what is doc. 5 above?
            return f'{author}, "{self.title}" {"in "+languages+")" if languages else ""}, {"("+self.other_info+", "+str(self.year)+")" if self.other_info and self.year else ""}'

        # elif other source_type keep existing system
        if self.journal:
            parts.append(self.journal)
        if self.volume:
            parts.append(self.volume)
        if self.year:
            parts.append("(%d)" % self.year)
        if self.other_info:
            parts.append(self.other_info)

        # title, journal, etc should be joined by spaces only
        ref = " ".join(parts)

        # delimit with comma whichever values are set
        return ", ".join([val for val in (author, ref) if val])

    def all_authors(self):
        """semi-colon delimited list of authors in order"""
        return "; ".join([str(c.creator) for c in self.authorship_set.all()])

    all_authors.short_description = "Authors"
    all_authors.admin_order_field = "first_author"  # set in admin queryset


class FootnoteQuerySet(models.QuerySet):
    def includes_footnote(self, other, include_content=True):
        """Check if the current queryset includes a match for the
        specified footnotes. Matches are made by comparing content source,
        location, document relation type, notes, and content (ignores
        associated content object). To ignore content when comparing
        footnotes, specify `include_content=False`.
        Returns the matching object if there was one, or False if not."""

        compare_fields = ["source", "location", "notes"]
        # optionally include content when comparing; include by default
        if include_content:
            compare_fields.append("content")

        for fn in self.all():
            if (
                all(getattr(fn, val) == getattr(other, val) for val in compare_fields)
                # NOTE: fn.doc_relation seems to be different on queryset footnote
                # than newly created object; check by display value to avoid problems
                and fn.get_doc_relation_display() == other.get_doc_relation_display()
            ):
                return fn

        return False


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
        (EDITION, _("Edition")),
        (TRANSLATION, _("Translation")),
        (DISCUSSION, _("Discussion")),
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
        "URL", blank=True, max_length=300, help_text="Link to the source (optional)"
    )

    # Generic relationship
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="corpus"),
    )
    object_id = GfkLookupField("content_type")
    content_object = GenericForeignKey()

    # replace default queryset with customized version
    objects = FootnoteQuerySet.as_manager()

    class Meta:
        ordering = ["source", "location"]

    def __str__(self):
        choices = dict(self.DOCUMENT_RELATION_TYPES)

        rel = " and ".join([str(choices[c]) for c in self.doc_relation]) or "Footnote"
        return f"{rel} of {self.content_object}"

    def has_transcription(self):
        """Admin display field indicating presence of digitized transcription."""
        return bool(self.content)

    has_transcription.short_description = "Digitized Transcription"
    has_transcription.boolean = True
    has_transcription.admin_order_field = "content"

    def display(self):
        """format footnote for display; used on document detail page
        and metdata export for old pgp site"""
        # source, location. notes
        # source. notes
        # source, location.
        parts = [str(self.source)]
        if self.location:
            parts.extend([", ", self.location])
        parts.append(".")
        if self.notes:
            parts.extend([" ", self.notes])
        return "".join(parts)

    def has_url(self):
        """Admin display field indicating if footnote has a url."""
        return bool(self.url)

    has_url.boolean = True
    has_url.admin_order_field = "url"

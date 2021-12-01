from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.humanize.templatetags.humanize import ordinal
from django.db import models
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from gfklookupwidget.fields import GfkLookupField
from modeltranslation.manager import MultilingualManager
from multiselectfield import MultiSelectField

from geniza.common.models import TrackChangesModel


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
    publisher = models.CharField(
        max_length=255,
        blank=True,
        help_text="Publisher name, or degree granting institution for a dissertations",
    )
    place_published = models.CharField(
        max_length=255, blank=True, help_text="Place where the work was published"
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
        """strip HTML tags and trailing period from formatted display"""
        return strip_tags(self.formatted_display(extra_fields=False))[:-1]

    def all_authors(self):
        """semi-colon delimited list of authors in order"""
        return "; ".join([str(c.creator) for c in self.authorship_set.all()])

    def formatted_display(self, extra_fields=True):
        """Format source for display; used on document scholarship page.
        To omit publisher, place_published, and page_range fields,
        specify `extra_fields=False`."""

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

        parts = []
        url = self.url

        if not url:
            for fn in self.footnote_set.all():
                if fn.url:
                    url = fn.url
                    break

        # Ensure that Unicode LTR mark is added after fields when RTL languages present
        rtl_langs = ["Hebrew", "Arabic", "Judaeo-Arabic"]
        source_langs = [str(lang) for lang in self.languages.all()]
        source_contains_rtl = set(source_langs).intersection(set(rtl_langs))
        ltr_mark = chr(8206) if source_contains_rtl else ""

        # Types that should receive double quotes around title
        doublequoted_types = ["Article", "Dissertation", "Book Section"]

        # Handle title
        work_title = ""
        if self.title:
            # if this is a book, italicize title
            if self.source_type.type == "Book":
                work_title = "<em>%s%s</em>" % (self.title, ltr_mark)
            # if this is a doublequoted type, wrap title in quotes
            elif self.source_type.type in doublequoted_types:
                stripped_title = self.title.strip("\"'")
                work_title = '"%s%s"' % (stripped_title, ltr_mark)
            # otherwise, just leave unformatted
            else:
                work_title = self.title + ltr_mark
        elif self.source_type and self.source_type.type and extra_fields:
            # Use type as descriptive title when no title available, per CMS
            work_title = self.source_type.type.lower()

        # Wrap title in link to URL
        if url and work_title:
            parts.append('<a href="%s">%s</a>' % (url, work_title))
        elif work_title:
            parts.append(work_title)

        # Add non-English languages as parenthetical
        non_english_langs = 0
        if self.languages.count():
            for lang in self.languages.all():
                if "English" not in str(lang):
                    non_english_langs += 1
                    parts.append("(in %s)" % lang)

        # Handling presence of book/journal title
        if self.journal:
            # add comma inside doublequotes when they are present, if no language parenthetical
            # examples:
            #   "Title"                 --> "Title,"
            #   NOT "Title" (in Hebrew) --> "Title," (in Hebrew)
            if self.title and (
                self.source_type.type in doublequoted_types
                and not non_english_langs  # put comma after language even when doublequotes present
            ):
                # find rightmost doublequote
                formatted_title = parts[-1]
                last_dq = formatted_title.rindex('"')
                # add comma directly before it
                parts[-1] = formatted_title[:last_dq] + "," + formatted_title[last_dq:]
            # otherwise, simply add the comma at the end of the title (or language)
            # examples:
            #   <em>Title</em>      --> <em>Title</em>,
            #   "Title" (in Hebrew) --> "Title" (in Hebrew),
            elif len(parts):
                parts[-1] += ","

            # CMS needs "in" before book title
            if self.source_type.type == "Book Section":
                parts.append("in")

            # italicize book/journal title
            parts.append("<em>%s%s</em>" % (self.journal, ltr_mark))

        # Unlike other work types, journal articles' volume/issue numbers
        # appear before the publisher info and date
        if self.source_type.type == "Article":
            if self.volume:
                parts.append(self.volume)
            # TODO: Add issue number to model or remove below
            # if self.issue:
            # parts[-1] += ","
            # parts.append("no. %d" % self.issue)

        if extra_fields:
            # Location, publisher, and date (omit for unpublished, unless it has a year)
            # examples:
            #   (n.p., n.d.)
            #   (n.p., 2013)
            #   (Oxford: n.p., 2013)
            #   (n.p.: Oxford University Press, 2013)
            #   (Oxford: Oxford University Press, 2013)
            #   (PhD diss., n.p., n.d.)
            #   (PhD diss., n.p., 2013)
            #   (PhD diss., Oxford University, 2013)
            if not (self.source_type.type == "Unpublished" and not self.year):
                # If publisher name present, assign it to "pubname", otherwise assign n.p.
                pub_name = "n.p." if not self.publisher else self.publisher
                if self.source_type.type == "Dissertation":
                    # Add "PhD diss." and degree granting institution for dissertation
                    # (do not include place published here)
                    pub_data = "PhD diss., %s" % pub_name
                elif self.place_published or self.publisher:
                    # Add publisher information for all other works, if available
                    if self.place_published:
                        pub_data = "%s: %s" % (self.place_published, pub_name)
                    else:
                        pub_data = "n.p.: %s" % pub_name
                else:
                    # If not a dissertation and no publisher info, then just use n.p.
                    pub_data = pub_name

                pub_year = "n.d." if not self.year else str(self.year)
                parts.append("(%s, %s)" % (pub_data, pub_year))
        elif self.year:
            # when extra fields disabled, show year only
            parts.append("(%s)" % str(self.year))

        # omit volumes for unpublished sources
        # (those volumes are an admin convienence for managing Goitein content)
        # and for articles (appears earlier in citation)
        needs_volume = bool(
            self.volume and self.source_type.type not in ["Article", "Unpublished"]
        )

        if extra_fields and self.page_range:
            # Page range and/or volume at end of citation
            parts[-1] += ","
            if needs_volume:
                parts.append("%s:%s" % (self.volume, self.page_range))
            else:
                parts.append(self.page_range)
        elif needs_volume:
            # Just volume at end of citation
            parts[-1] += ","
            if self.source_type.type == "Book":
                parts.append("vol.")
            parts.append(self.volume)

        # title and other metadata should be joined by spaces
        ref = " ".join(parts)

        # delimit with comma only if title present and extra_fields is true
        delimiter = ", " if work_title and extra_fields else " "

        return delimiter.join([val for val in (author, ref) if val]) + "."

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

    def editions(self):
        """Filter to all footnotes that provide editions/transcriptions."""
        return self.filter(doc_relation__contains=Footnote.EDITION)


class Footnote(TrackChangesModel):
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

    def content_text(self):
        "content as plain text, if available"
        if self.content:
            return self.content.get("text")

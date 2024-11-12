import re
from collections import defaultdict
from functools import cached_property
from os import path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.humanize.templatetags.humanize import ordinal
from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import NullIf
from django.db.models.query import Prefetch
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from gfklookupwidget.fields import GfkLookupField
from modeltranslation.manager import MultilingualManager, MultilingualQuerySet
from multiselectfield import MultiSelectField

from geniza.common.fields import NaturalSortField
from geniza.common.models import TrackChangesModel
from geniza.footnotes.utils import HTMLLineNumberParser


class SourceType(models.Model):
    """type of source"""

    type = models.CharField(max_length=255)

    def __str__(self):
        return self.type


class SourceLanguage(models.Model):
    """language of a source document"""

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=10, help_text="ISO language code")
    LTR = "ltr"
    RTL = "rtl"
    DIRECTION_CHOICES = ((LTR, "Left to right"), (RTL, "Right to left"))
    direction = models.CharField(max_length=3, default=LTR, choices=DIRECTION_CHOICES)

    def __str__(self):
        return self.name


class CreatorManager(MultilingualManager):
    """Custom manager for :class:`Creator` with natural key lookup"""

    def get_by_natural_key(self, last_name, first_name):
        """natural key lookup: based on combination of last name and first name"""
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
        """natural key: tuple of last name, first name"""
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


class SourceQuerySet(MultilingualQuerySet):
    """Custom queryset for :class:`Source`, for reusable
    prefetching and count annotation."""

    def metadata_prefetch(self):
        "prefetch source type and authors"
        return self.select_related("source_type").prefetch_related(
            "languages",
            Prefetch(
                "authorship_set",
                queryset=Authorship.objects.select_related("creator"),
            ),
        )

    def footnote_count(self):
        "annotate with footnote count"
        return self.annotate(Count("footnote", distinct=True))


class Source(models.Model):
    """a published or unpublished work related to geniza materials"""

    authors = models.ManyToManyField(Creator, through=Authorship)
    title = models.CharField(max_length=255, blank=True, null=True)
    year = models.PositiveIntegerField(blank=True, null=True)
    edition = models.PositiveIntegerField(blank=True, null=True)
    volume = models.CharField(
        max_length=255,
        blank=True,
        help_text="Volume of a multivolume book, or journal volume for an article",
    )
    issue = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Issue number for a journal article",
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
        help_text="Publisher name, or degree granting institution for a dissertation",
    )
    place_published = models.CharField(
        max_length=255, blank=True, help_text="Place where the work was published"
    )
    other_info = models.TextField(
        blank=True, help_text="Additional citation information, if any"
    )
    source_type = models.ForeignKey(
        SourceType,
        on_delete=models.CASCADE,
        help_text="""The form of the source's publication. Note: for unpublished sources, be sure
        to create separate Source records for unpublished transcriptions and unpublished
        translations, even if they reside on the same digital document.""",
    )
    languages = models.ManyToManyField(
        SourceLanguage,
        help_text="""The language(s) the source is written in. Note: The Unspecified language
        option should only ever be used for unpublished transcriptions, as the language of the
        transcription is already marked on the document.""",
    )
    url = models.URLField(blank=True, max_length=300, verbose_name="URL")
    # preliminary place to store transcription text; should not be editable
    notes = models.TextField(blank=True)

    objects = SourceQuerySet.as_manager()

    class Meta:
        # set default order to title, year for now since first-author order
        # requires queryset annotation
        ordering = ["title", "year"]

    def __str__(self):
        """Method used for for internal/data admin use.
        Please use the `display` or `formatted_display` methods for public display."""
        # Append volume for unpublished
        if self.source_type.type == "Unpublished" and self.volume:
            return "%s (%s)" % (self.display(), self.volume)
        # Otherwise return formatted display without html tags
        else:
            return self.display()

    def all_authors(self):
        """semi-colon delimited list of authors in order"""
        return "; ".join([str(c.creator) for c in self.authorship_set.all()])

    def all_languages(self):
        """comma-delimited list of languages, in parentheses, used for the translation selector"""
        if self.languages.exists():
            langs = [
                str(lang)
                for lang in self.languages.all().order_by("name")
                if "Unspecified" not in str(lang)
            ]
            if langs:
                return "(in %s)" % ", ".join(langs)
        return ""

    def formatted_display(self, extra_fields=True, format_index_cards=False):
        """Format source for display; used on document scholarship page.
        To omit publisher, place_published, and page_range fields,
        specify `extra_fields=False`."""

        author = ""
        if len(self.authorship_set.all()):
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
            # if this is a machine learning model, format appropriately
            elif "model" in self.source_type.type:
                work_title = "Machine-generated transcription (%s)" % self.title
            elif (
                format_index_cards
                and "Goitein" in author
                and "index card" in self.title.lower()
            ):
                work_title = "unpublished index cards (1950–85)"
            # otherwise, just leave unformatted
            else:
                work_title = self.title + ltr_mark
        elif extra_fields or not author:
            # Use [digital geniza document edition] as placeholder title when no title available;
            # only when extra_fields enabled, or there is no author

            # Translators: Placeholder for when a work has no title available
            work_title = gettext("[digital geniza document edition]")

        # Wrap title in link to URL
        if self.url and work_title:
            parts.append('<a href="%s">%s</a>' % (self.url, work_title))
        elif work_title:
            parts.append(work_title)

        # Add edition for Book type if present
        if self.edition:
            edition_str = "%s ed." % ordinal(self.edition)
            if self.source_type.type == "Book" and self.title:
                parts[-1] += ","
                parts.append(edition_str)

        # Add non-English languages as parenthetical
        included_langs = 0
        if self.languages.exists():
            for lang in self.languages.all():
                # Also prevent Unspecified from showing up in source citations
                if "English" not in str(lang) and "Unspecified" not in str(lang):
                    included_langs += 1
                    parts.append("(in %s)" % lang)

        # Handling presence of book/journal title
        if self.journal:
            # add comma inside doublequotes when they are present, if no language parenthetical
            # examples:
            #   "Title"                 --> "Title,"
            #   NOT "Title" (in Hebrew) --> "Title," (in Hebrew)
            if self.title and (
                self.source_type.type in doublequoted_types
                and not included_langs  # put comma after language even when doublequotes present
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

            if self.source_type.type == "Book Section" and self.edition:
                parts[-1] += ","
                parts.append(edition_str)

        # Unlike other work types, journal articles' volume/issue numbers
        # appear before the publisher info and date
        if self.source_type.type == "Article":
            if self.volume:
                parts.append(self.volume)
            if self.issue:
                parts[-1] += ","
                parts.append("no. %d" % self.issue)

        if extra_fields and not "model" in self.source_type.type:
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
            if "Book" in self.source_type.type:
                parts.append("vol.")
            parts.append(self.volume)

        # title and other metadata should be joined by spaces
        ref = " ".join(parts)

        # use comma delimiter after authors when it does not break citation;
        # i.e. extra_fields is true, source has a title, or source has a journal
        # and no non-english languages to list.
        # examples:
        #   Allony (in Hebrew), Journal 6 (1964)    (no comma)
        #   L. B. Yarbrough (in Hebrew)             (no comma)
        #   Author (1964)                           (no comma)
        #   Author, Journal 6 (1964)                (comma)
        #   Author, [digital geniza document edition]                      (comma)
        use_comma = (
            extra_fields
            or self.title
            or (self.journal and not included_langs)
            or self.source_type.type == "Unpublished"
        )
        delimiter = ", " if use_comma else " "

        # rstrip to prevent double periods (e.g. in the case of trailing edition abbreviation)
        return delimiter.join([val for val in (author, ref) if val]).rstrip(".") + "."

    all_authors.short_description = "Authors"
    all_authors.admin_order_field = "first_author"  # set in admin queryset

    def display(self):
        """strip HTML tags from formatted display"""
        return strip_tags(self.formatted_display(extra_fields=False))

    @classmethod
    def get_volume_from_shelfmark(cls, shelfmark):
        """Given a shelfmark, get our volume label. This logic was determined in
        migration 0011_split_goitein_typedtexts.py
        """
        if shelfmark.startswith("T-S"):
            volume = shelfmark[0:6]
            volume = "T-S Misc" if volume == "T-S Mi" else volume
        else:
            volume = shelfmark.split(" ")[0]
        return volume

    @property
    def uri(self):
        """Generate a URI for this source to be used in transcription annotations,
        in order to filter them by associated source"""
        # TODO: add a minimal view with json representation of the source so that this uri resolves
        manifest_base_url = getattr(settings, "ANNOTATION_MANIFEST_BASE_URL", "")
        return urljoin(manifest_base_url, path.join("sources", str(self.pk))) + "/"

    @staticmethod
    def id_from_uri(uri):
        """Given a URi for a source (as used in transcription annotations), return
        the source id"""
        # TODO: Use resolve() when the json source view exists
        # (see logic in equivalent Document method)
        return int(uri.split("/")[-2])

    @classmethod
    def from_uri(cls, uri):
        """Given a URI for a Source (as used in transcription annotations), return the Source
        object matching the pk"""
        return cls.objects.get(pk=Source.id_from_uri(uri))


class FootnoteQuerySet(models.QuerySet):
    def includes_footnote(self, other):
        """Check if the current queryset includes a match for the
        specified footnote. Matches are made by comparing content source,
        location, document relation type, and notes.
        Returns the matching object if there was one, or False if not."""

        compare_fields = ["source", "location", "emendations", "notes"]

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

    def metadata_prefetch(self):
        "prefetch source, source authors, and content object"
        return self.select_related("source").prefetch_related(
            "content_object", "source__authorship_set__creator"
        )


class Footnote(TrackChangesModel):
    """a footnote that links a :class:`~geniza.corpus.models.Document` to a :class:`Source`"""

    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Location within the source "
        + "(e.g., document number or page range)",
    )
    location_sort = NaturalSortField(for_field="location")

    EDITION = "E"
    TRANSLATION = "T"
    DISCUSSION = "D"
    DIGITAL_EDITION = "X"
    DIGITAL_TRANSLATION = "Y"
    DOCUMENT_RELATION_TYPES = (
        (EDITION, _("Edition")),
        (TRANSLATION, _("Translation")),
        (DISCUSSION, _("Discussion")),
        (DIGITAL_EDITION, "Digital Edition"),
        (DIGITAL_TRANSLATION, "Digital Translation"),
    )

    doc_relation = MultiSelectField(
        "Document relation",
        choices=DOCUMENT_RELATION_TYPES,
        help_text="How does the source relate to this document? "
        + 'Please note: "Edition" is a (published or unpublished) '
        + 'transcription. "Digital edition" is the PGP version of an '
        + "edition, and the source record should NOT be deleted. Footnotes "
        + 'for "editions" and "digital editions" should NOT be combined, '
        + "even if they refer to the same transcription.",
        null=True,
        blank=True,
    )
    emendations = models.CharField(
        "minor emendations by",
        max_length=512,
        help_text="Displays publicly. For minor emendations to a "
        + "transcription or translation (not including typo corrections), "
        + "enter Your Name, Year. May include multiple names and dates. For "
        + "significant alterations to a transcription or translation, create "
        + "a new source indicating co-authorship.",
        null=True,
        blank=True,
    )
    notes = models.TextField(
        help_text="Additional context. Only visible to admins/editors.",
        blank=True,
    )
    content = models.JSONField(
        blank=True,
        null=True,
        help_text="Transcription content (transitional; edit with care and only when needed)",
    )
    url = models.URLField(
        "URL", blank=True, max_length=300, help_text="Link to the source (optional)"
    )

    # Generic relationship
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="corpus") | models.Q(app_label="entities"),
    )
    object_id = GfkLookupField(
        "content_type", help_text="If content type is Document, this is PGPID"
    )
    content_object = GenericForeignKey()

    # replace default queryset with customized version
    objects = FootnoteQuerySet.as_manager()

    class Meta:
        ordering = [
            "source",
            # sort footnote with empty locations after footnote with location
            # (sort digital editions after other footnotes for same source)
            NullIf("location_sort", models.Value("")).asc(nulls_last=True),
        ]
        constraints = [
            # only allow one digital edition per source for a document
            models.UniqueConstraint(
                fields=("source", "object_id", "content_type"),
                name="one_digital_edition_per_document_and_source",
                condition=models.Q(doc_relation__contains="X"),  # X = DIGITAL_EDITION
            ),
            # only allow one digital translation per source for a document
            models.UniqueConstraint(
                fields=("source", "object_id", "content_type"),
                name="one_digital_translation_per_document_and_source",
                condition=models.Q(
                    doc_relation__contains="Y"
                ),  # Y = DIGITAL_TRANSLATION
            ),
        ]

    def __str__(self):
        choices = dict(self.DOCUMENT_RELATION_TYPES)

        rel = (
            " and ".join([str(choices[c]) for c in (self.doc_relation or [])])
            or "Footnote"
        )
        return f"{rel} of {self.content_object}"

    def display(self):
        """format footnote for display; used on document detail page
        and metadata export for old pgp site"""
        # source, location. notes.
        # source. notes.
        # source, location.
        parts = [self.source.display()]
        if self.notes:
            # uppercase first letter of notes if not capitalized
            notes = self.notes[0].upper() + self.notes[1:]
            # append period to notes if not present
            parts.extend([" ", notes.strip("."), "."])
        return "".join(parts)

    def has_url(self):
        """Admin display field indicating if footnote has a url."""
        return bool(self.url)

    has_url.boolean = True
    has_url.admin_order_field = "url"

    @cached_property
    def content_html(self):
        """content as html, if available; returns a dictionary of lists.
        keys are canvas ids, list is html content."""
        # NOTE: previously only returned if type was digital edition;
        # now that we're using foreign keys, return content from
        # any associated annotations, regardless of what doc relation.

        # generate return a dictionary of lists of annotation html content
        # keyed on canvas uri
        # handle multiple annotations on the same canvas
        html_content = defaultdict(list)
        # order by optional position property (set by manual reorder in editor), then date
        for a in self.annotation_set.exclude(
            # only iterate through block-level annotations; we will group their lines together
            # if they have lines. (isnull check required to not exclude block-level annotations
            # missing the textGranularity attribute)
            Q(content__textGranularity__isnull=False)
            & Q(content__textGranularity="line")
        ).order_by("content__schema:position", "created"):
            html_content[a.target_source_id] += a.block_content_html
        # cast to a regular dict to avoid weirdness in django templates
        return dict(html_content)

    @cached_property
    def content_html_str(self):
        "content as a single string of html, if available"
        # content html is a dict; values are lists of html content
        content_html = self.content_html
        if content_html:
            return "\n".join(
                [
                    section
                    for canvas_annos in content_html.values()
                    for section in canvas_annos
                ]
            )

    @cached_property
    def content_text_canvases(self):
        """content as a list of strings, one per canvas"""
        # used for regex search indexing
        content_html = self.content_html
        if content_html:
            return [
                # convert each annotation from html to plaintext
                "\n".join(
                    [
                        # remove newlines so that multiline annotations can be searched
                        BeautifulSoup(a, features="lxml").get_text().replace("\n", " ")
                        for a in canvas_annos
                    ]
                )
                for canvas_annos in content_html.values()
            ]

    @staticmethod
    def explicit_line_numbers(html):
        """add explicit line numbers to passed HTML (in value attributes of ol > li)"""
        if html:  # don't attempt to parse if html is not set
            parser = HTMLLineNumberParser()
            parser.feed(html)
            return parser.html_str

    @property
    def content_text(self):
        "content as plain text, if available"
        # use beautiful soup to parse html content and return as text
        # (strips tags and convert entities to plain text equivalent)
        # but only return if we have content (otherwise returns string "None")
        if self.content_html_str:
            return BeautifulSoup(self.content_html_str, features="lxml").get_text()

    def iiif_annotation_content(self):
        """Return transcription content from this footnote (if any)
        as a IIIF annotation resource that can be associated with a canvas.
        """
        # For now, since we have no block/canvas information, return the
        # whole thing as a single resource
        html = self.content_html
        if html:
            # this is the content that should be set as the "resource"
            # of an annotation
            return {
                "@type": "cnt:ContentAsText",
                "format": "text/html",
                # language todo
                "chars": "<div dir='rtl' class='transcription'>%s</div>" % html,
            }

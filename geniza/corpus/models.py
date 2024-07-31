import logging
import re
from collections import defaultdict
from copy import deepcopy
from functools import cached_property
from itertools import chain

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Concat
from django.db.models.functions.text import Lower
from django.db.models.query import Prefetch
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from djiffy.models import Manifest
from modeltranslation.manager import MultilingualQuerySet
from parasolr.django.indexing import ModelIndexable
from piffle.image import IIIFImageClient
from piffle.presentation import IIIFException, IIIFPresentation
from requests.exceptions import ConnectionError
from taggit_selectize.managers import TaggableManager
from unidecode import unidecode
from urllib3.exceptions import HTTPError, NewConnectionError

from geniza.annotations.models import Annotation
from geniza.common.models import (
    DisplayLabelMixin,
    TrackChangesModel,
    cached_class_property,
)
from geniza.common.utils import absolutize_url
from geniza.corpus.annotation_utils import document_id_from_manifest_uri
from geniza.corpus.dates import DocumentDateMixin, PartialDate, standard_date_display
from geniza.corpus.iiif_utils import GenizaManifestImporter, get_iiif_string
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.footnotes.models import Creator, Footnote

logger = logging.getLogger(__name__)


class CollectionManager(models.Manager):
    """Custom manager for :class:`Collection` with natural key lookup"""

    def get_by_natural_key(self, name, library):
        """get by natural key: combination of name and library"""
        return self.get(name=name, library=library)


class Collection(models.Model):
    """Collection or library that holds Geniza fragments"""

    library = models.CharField(max_length=255, blank=True)  # optional
    lib_abbrev = models.CharField("Library Abbreviation", max_length=255, blank=True)
    abbrev = models.CharField("Collection Abbreviation", max_length=255, blank=True)
    name = models.CharField(
        "Collection Name",
        max_length=255,
        blank=True,
        help_text="Collection name, if different than Library",
    )
    location = models.CharField(
        max_length=255, help_text="Current location of the collection", blank=True
    )

    objects = CollectionManager()

    class Meta:
        # sort on the combination of these fields, since many are optional
        # NOTE: this causes problems for sorting related models in django admin
        # (i.e., sorting fragments by collection); see corpus admin for workaround
        ordering = [
            Concat(
                models.F("lib_abbrev"),
                models.F("abbrev"),
                models.F("name"),
                models.F("library"),
            )
        ]
        constraints = [
            # require at least one of library OR name
            models.CheckConstraint(
                check=(models.Q(library__regex=".+") | models.Q(name__regex=".+")),
                name="req_library_or_name",
            ),
            models.UniqueConstraint(
                fields=["library", "name"], name="unique_library_name"
            ),
        ]

    def __str__(self):
        # by default, combine abbreviations
        values = [val for val in (self.lib_abbrev, self.abbrev) if val]
        # but abbreviations are optional, so fallback to names
        if not values:
            values = [val for val in (self.name, self.library) if val]
        return ", ".join(values)

    def natural_key(self):
        """natural key: tuple of name and library"""
        return (self.name, self.library)


class LanguageScriptManager(models.Manager):
    """Custom manager for :class:`LanguageScript` with natural key lookup"""

    def get_by_natural_key(self, language, script):
        """get by natural key: combination of language and script"""
        return self.get(language=language, script=script)


class LanguageScript(models.Model):
    """Combination language and script"""

    language = models.CharField(max_length=255)
    script = models.CharField(max_length=255)
    display_name = models.CharField(
        max_length=255,
        blank=True,
        unique=True,
        null=True,
        help_text="Option to override the autogenerated language-script name",
    )
    iso_code = models.CharField(
        "ISO Code",
        max_length=3,
        blank=True,
        help_text="ISO 639 code for this language (2 or 3 letters)",
    )

    objects = LanguageScriptManager()

    class Meta:
        verbose_name = "Language + Script"
        verbose_name_plural = "Languages + Scripts"
        ordering = ["language"]
        constraints = [
            models.UniqueConstraint(
                fields=["language", "script"], name="unique_language_script"
            )
        ]

    def __str__(self):
        # Allow display_name to override autogenerated string
        # otherwise combine language and script
        #   e.g. Judaeo-Arabic (Hebrew script)
        return self.display_name or f"{self.language} ({self.script} script)"

    def natural_key(self):
        """natural key: tuple of language and script"""
        return (self.language, self.script)


class FragmentManager(models.Manager):
    """Custom manager for :class:`Fragment` with natural key lookup"""

    def get_by_natural_key(self, shelfmark):
        """get fragment by natural key: shelfmark"""
        return self.get(shelfmark=shelfmark)


class Fragment(TrackChangesModel):
    """A single fragment or multifragment held by a
    particular library or archive."""

    shelfmark = models.CharField(max_length=255, unique=True)
    # multiple, semicolon-delimited values. Keeping as single-valued for now
    old_shelfmarks = models.CharField(
        "Historical Shelfmarks",
        blank=True,
        max_length=500,
        help_text="Semicolon-delimited list of previously used shelfmarks; "
        + "automatically updated on shelfmark change.",
    )
    collection = models.ForeignKey(
        Collection, blank=True, on_delete=models.SET_NULL, null=True
    )
    url = models.URLField(
        "URL", blank=True, help_text="Link to library catalog record for this fragment."
    )
    iiif_url = models.URLField("IIIF URL", blank=True)
    is_multifragment = models.BooleanField(
        "Multifragment",
        default=False,
        help_text="True if there are multiple fragments in one shelfmark",
    )
    provenance = models.TextField(
        blank=True, help_text="The origin and acquisition history of this fragment."
    )
    notes = models.TextField(blank=True)
    needs_review = models.TextField(
        blank=True,
        help_text="Enter text here if an administrator needs to review this fragment.",
    )

    manifest = models.ForeignKey(Manifest, null=True, on_delete=models.SET_NULL)

    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    objects = FragmentManager()

    # NOTE: may want to add optional ForeignKey to djiffy Manifest here
    # (or property to find by URI if not an actual FK)

    class Meta:
        ordering = ["shelfmark"]

    def __str__(self):
        return self.shelfmark

    def natural_key(self):
        """natural key: shelfmark"""
        return (self.shelfmark,)

    def iiif_images(self):
        """IIIF image URLs for this fragment. Returns a list of
        :class:`~piffle.image.IIIFImageClient` and corresponding list of labels,
        or None if this fragement has no IIIF url associated."""

        # if there is no iiif for this fragment, bail out
        if not self.iiif_url:
            return None
        images = []
        labels = []
        canvases = []
        # use images from locally cached manifest if possible
        if self.manifest:
            manifest_canvases = self.manifest.canvases.all()
            # handle no canvases on manifest; cached QS will not incur extra DB hit
            if not manifest_canvases.count():
                return None
            else:
                for canvas in manifest_canvases:
                    images.append(canvas.image)
                    labels.append(canvas.label)
                    canvases.append(canvas.uri)

        # if not cached, load from remote url
        else:
            try:
                manifest = IIIFPresentation.from_url(self.iiif_url)
                for canvas in manifest.sequences[0].canvases:
                    image_id = canvas.images[0].resource.service.id
                    images.append(IIIFImageClient(*image_id.rsplit("/", 1)))
                    # label provides library's recto/verso designation
                    labels.append(canvas.label)
                    canvases.append(canvas.uri)
            except (IIIFException, ConnectionError, HTTPError):
                logger.warning("Error loading IIIF manifest: %s" % self.iiif_url)
                return None

        return images, labels, canvases

    @staticmethod
    def admin_thumbnails(images, labels, canvases=[], selected=[]):
        """Convenience method for generating IIIF thumbnails HTML from lists of images and labels;
        separated for reuse in Document"""
        return mark_safe(
            " ".join(
                # include label as title for now; include canvas as data attribute for reordering
                # on Document
                '<div class="admin-thumbnail%s" %s><img src="%s" loading="lazy" height="%d" title="%s" /></div>'
                % (
                    " selected" if i in selected else "",
                    f'data-canvas="{list(canvases)[i]}"' if canvases else "",
                    img,
                    img.size.options["height"] if hasattr(img, "size") else 200,
                    labels[i],
                )
                for i, img in enumerate(images)
            )
        )

    def iiif_thumbnails(self, selected=[]):
        """html for thumbnails of iiif image, for display in admin"""
        iiif_images = self.iiif_images()
        if iiif_images is None:
            # if there are no iiif images for this fragment, use placeholder
            # images for recto/verso side selection
            recto_img = static("img/ui/all/all/recto-placeholder.svg")
            verso_img = static("img/ui/all/all/verso-placeholder.svg")
            image_urls = [recto_img, verso_img]
            labels = ["recto", "verso"]
        else:
            images, labels, _ = iiif_images
            image_urls = [img.size(height=200) for img in images]
        return Fragment.admin_thumbnails(image_urls, labels, selected=selected)

    # CUDL manifests attribution include a metadata statement, but it
    # is not relevant for us since we aren't displaying their metadata
    cudl_metadata_str = "This metadata is published free of restrictions, under the terms of the Creative Commons CC0 1.0 Universal Public Domain Dedication."

    @property
    def attribution(self):
        """Generate an attribution for this fragment"""
        # pull from locally cached manifest
        # (don't hit remote url if not cached)
        if self.manifest:
            attribution = get_iiif_string(
                self.manifest.extra_data.get("attribution", "")
            )
            if attribution:
                # Remove CUDL metadata string from displayed attribution
                return mark_safe(
                    attribution.replace(self.cudl_metadata_str, "").strip()
                )

    @property
    @admin.display(description="Provenance from IIIF manifest")
    def iiif_provenance(self):
        """Generate a provenance statement for this fragment from IIIF"""
        if self.manifest and self.manifest.metadata:
            return get_iiif_string(self.manifest.metadata.get("Provenance", ""))

    def clean(self):
        """Custom validation and cleaning; currently only :meth:`clean_iiif_url`"""
        self.clean_iiif_url()

    def clean_iiif_url(self):
        """Remove redundant manifest parameter from IIIF url when present"""
        # some iiif viewers have a terrible convention of repeating the full manifest
        # url in a query string; strip that out if it's there
        self.iiif_url = self.iiif_url.split("?manifest=")[0]

    def save(self, *args, **kwargs):
        """Remember how shelfmarks have changed by keeping a semi-colon list
        in the old_shelfmarks field"""
        if self.pk and self.has_changed("shelfmark"):
            if self.old_shelfmarks:
                old_shelfmarks = set(self.old_shelfmarks.split(";"))
                old_shelfmarks.add(self.initial_value("shelfmark"))
                self.old_shelfmarks = ";".join(old_shelfmarks - {self.shelfmark})
            else:
                self.old_shelfmarks = self.initial_value("shelfmark")

        # if iiif url is set and manifest is not available, or iiif url has changed,
        # import the manifest
        if self.iiif_url and not self.manifest or self.has_changed("iiif_url"):
            # if iiif url has changed and there is a value, import and update
            if self.iiif_url:
                try:
                    # importer should return the relevant manifest
                    # (either newly imported or already in the database)
                    imported = GenizaManifestImporter().import_paths([self.iiif_url])
                    self.manifest = imported[0] if imported else None
                except (IIIFException, NewConnectionError):
                    # clear out the manifest if there was an error
                    self.manifest = None
                    # if saved via admin, alert the user
                    if hasattr(self, "request"):
                        messages.error(self.request, "Error loading IIIF manifest")

                # if there was no error but manifest is unset, warn
                if self.manifest is None and hasattr(self, "request"):
                    messages.warning(self.request, "Failed to cache IIIF manifest")
            else:
                # otherwise, clear the associated manifest (iiif url has been removed)
                self.manifest = None

        super(Fragment, self).save(*args, **kwargs)


class DocumentTypeManager(models.Manager):
    """Custom manager for :class:`DocumentType` with natural key lookup"""

    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class DocumentType(DisplayLabelMixin, models.Model):
    """Controlled vocabulary of document types."""

    name = models.CharField(max_length=255, unique=True)
    display_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional label for display on the public site",
    )
    objects = DocumentTypeManager()

    @cached_class_property
    def objects_by_label(cls):
        return super().objects_by_label()


class DocumentSignalHandlers:
    """Signal handlers for indexing :class:`Document` records when
    related records are saved or deleted."""

    # lookup from model verbose name to attribute on documents
    # for use in queryset filter
    model_filter = {
        "fragment": "fragments",
        "tag": "tags",
        "document type": "doctype",
        "tagged item": "tagged_items",
        "Related Fragment": "textblock",  # textblock verbose name
        "footnote": "footnotes",
        "source": "footnotes__source",
        "creator": "footnotes__source__authorship__creator",
        "annotation": "footnotes__annotation",
    }

    @staticmethod
    def related_change(instance, raw, mode):
        """reindex all associated documents when related data is changed"""
        # common logic for save and delete
        # raw = saved as presented; don't query the database
        if raw or not instance.pk:
            return
        # get related lookup for document filter
        model_name = instance._meta.verbose_name
        doc_attr = DocumentSignalHandlers.model_filter.get(model_name)
        # if handler fired on an model we don't care about, warn and exit
        if not doc_attr:
            logger.warning(
                "Indexing triggered on %s but no document attribute is configured"
                % model_name
            )
            return

        doc_filter = {"%s__pk" % doc_attr: instance.pk}
        docs = Document.items_to_index().filter(**doc_filter)
        if docs.exists():
            logger.debug(
                "%s %s, reindexing %d related document(s)",
                model_name,
                mode,
                docs.count(),
            )
            ModelIndexable.index_items(docs)

    @staticmethod
    def related_save(sender, instance=None, raw=False, **_kwargs):
        """reindex associated documents when a related object is saved"""
        # delegate to common method
        DocumentSignalHandlers.related_change(instance, raw, "save")

    @staticmethod
    def related_delete(sender, instance=None, raw=False, **_kwargs):
        """reindex associated documents when a related object is deleted"""
        # delegate to common method
        DocumentSignalHandlers.related_change(instance, raw, "delete")


class TagSignalHandlers:
    """Signal handlers for :class:`taggit.Tag` records."""

    @staticmethod
    def unidecode_tag(sender, instance, **kwargs):
        """Convert saved tags to ascii, stripping diacritics."""
        instance.name = unidecode(instance.name)

    @staticmethod
    def tagged_item_change(sender, instance, action, **kwargs):
        """Ensure document (=instance) is indexed after the tags m2m relationship is saved and the
        list of tags is pulled from the database, on any tag change."""
        if action in ["post_add", "post_remove", "post_clear"]:
            logger.debug("taggit.TaggedItem %s, reindexing related document", action)
            ModelIndexable.index_items(Document.objects.filter(pk=instance.pk))


class DocumentQuerySet(MultilingualQuerySet):
    def metadata_prefetch(self):
        """
        Returns a further QuerySet that has been prefetched for relevant document information.
        """
        return self.select_related("doctype").prefetch_related(
            "tags",
            "languages",
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment", "fragment__collection"
                ),
            ),
        )
        # NOTE: footnotes likely should be prefetched depending on use case,
        # but nested prefetching may vary

    def get_by_any_pgpid(self, pgpid):
        """Find a document by current or old pgpid"""
        return self.get(models.Q(id=pgpid) | models.Q(old_pgpids__contains=[pgpid]))


class PermalinkMixin:
    """Mixin to generate a permalink for Django model objects by removing language code
    from the object's absolute URL."""

    @property
    def permalink(self):
        # generate permalink without language url so that all versions have
        # the same link and users will be directed to their preferred language
        # - get current active language, or default language if not active
        lang = get_language() or settings.LANGUAGE_CODE
        return absolutize_url(self.get_absolute_url().replace(f"/{lang}/", "/"))


class Document(ModelIndexable, DocumentDateMixin, PermalinkMixin):
    """A unified document such as a letter or legal document that
    appears on one or more fragments."""

    id = models.AutoField("PGPID", primary_key=True)

    fragments = models.ManyToManyField(
        Fragment, through="TextBlock", related_name="documents"
    )
    image_overrides = models.JSONField(
        null=False, blank=True, default=dict, verbose_name="Image Order/Rotation"
    )
    shelfmark_override = models.CharField(
        "Shelfmark Override",
        blank=True,
        max_length=500,
        help_text="Override default shelfmark display, e.g. to indicate a range of shelfmarks.",
    )
    description = models.TextField(blank=True)
    doctype = models.ForeignKey(
        DocumentType,
        blank=True,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Type",
        help_text='Refer to <a href="%s" target="_blank">PGP Document Type Guide</a>'
        % settings.PGP_DOCTYPE_GUIDE,
    )
    tags = TaggableManager(blank=True, related_name="tagged_document")
    languages = models.ManyToManyField(
        LanguageScript, blank=True, verbose_name="Primary Languages"
    )
    secondary_languages = models.ManyToManyField(
        LanguageScript, blank=True, related_name="secondary_document"
    )
    language_note = models.TextField(
        blank=True, help_text="Notes on diacritics, vocalisation, etc."
    )
    notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    needs_review = models.TextField(
        blank=True,
        help_text="Enter text here if an administrator needs to review this document.",
    )
    old_pgpids = ArrayField(models.IntegerField(), null=True, verbose_name="Old PGPIDs")

    objects = DocumentQuerySet.as_manager()

    PUBLIC = "P"
    STATUS_PUBLIC = "Public"
    SUPPRESSED = "S"
    STATUS_SUPPRESSED = "Suppressed"
    STATUS_CHOICES = (
        (PUBLIC, STATUS_PUBLIC),
        (SUPPRESSED, STATUS_SUPPRESSED),
    )
    PUBLIC_LABEL = "Public"
    #: status of record; currently choices are public or suppressed
    status = models.CharField(
        max_length=2,
        choices=STATUS_CHOICES,
        default=PUBLIC,
        help_text="Decide whether a document should be publicly visible",
    )
    events = models.ManyToManyField(
        to="entities.Event",
        related_name="documents",
        verbose_name="Related Events",
        through="DocumentEventRelation",
    )
    footnotes = GenericRelation(Footnote, related_query_name="document")
    log_entries = GenericRelation(LogEntry, related_query_name="document")

    # Placeholder canvas to use when not all IIIF images are available
    PLACEHOLDER_CANVAS = {
        "image": {
            "info": static("img/ui/all/all/image-unavailable.png"),
        },
        "placeholder": True,
    }

    # NOTE: default ordering disabled for now because it results in duplicates
    # in django admin; see admin for ArrayAgg sorting solution
    class Meta:
        pass
        # abstract = False
        # ordering = [Least('textblock__fragment__shelfmark')]

    def __str__(self):
        return f"{self.shelfmark_display or '??'} (PGPID {self.id or '??'})"

    def save(self, *args, **kwargs):
        # update standardized date if appropriate/supported
        # TODO: could improve by making use of track changes;
        # should we overwrite standard if original changed?
        try:
            self.standardize_date(update=True)
        except ValueError as e:
            # report to user when called via django admin and request is set
            if hasattr(self, "request"):
                messages.warning(self.request, "Error standardizing date: %s" % e)
            # otherwise ignore (unsupported date format)

        # cleanup unicode \xa0 from description, in all translated languages
        for lang_code, _ in settings.LANGUAGES:
            desc = getattr(self, "description_%s" % lang_code)
            if desc:
                # normalize to ascii space
                desc = re.sub(r"[\xa0 ]+", " ", desc)
                setattr(self, "description_%s" % lang_code, desc)

        super().save(*args, **kwargs)

    # NOTE: inherits clean() method from DocumentDateMixin
    # make sure to call super().clean() if extending!

    @classmethod
    def from_manifest_uri(cls, uri):
        """Given a manifest URI (as used in transcription annotations), find a Document matching
        its pgpid"""
        # will raise Resolver404 if url does not resolve
        return cls.objects.get(pk=document_id_from_manifest_uri(uri))

    @property
    def shelfmark(self):
        """shelfmarks for associated fragments"""
        # access via textblock so we follow specified order,
        # use dict keys to ensure unique
        return " + ".join(
            dict.fromkeys(
                block.fragment.shelfmark
                for block in self.textblock_set.all()
                if block.certain  # filter locally instead of in the db
            )
        )

    @property
    @admin.display(description="Shelfmark", ordering="shelfmk_all")
    def shelfmark_display(self):
        """Label for this document; by default, based on the combined shelfmarks from all certain
        associated fragments; uses :attr:`shelfmark_override` if set"""
        return self.shelfmark_override or self.shelfmark

    @property
    @admin.display(description="Historical shelfmarks")
    def fragment_historical_shelfmarks(self):
        """Property to display set of all historical shelfmarks on the document"""
        all_textblocks = self.textblock_set.all()
        all_fragments = [tb.fragment for tb in all_textblocks]
        return "; ".join(
            [frag.old_shelfmarks for frag in all_fragments if frag.old_shelfmarks]
        )

    @property
    def collection(self):
        """collection (abbreviation) for associated fragments"""
        # use set to ensure unique; sort for reliable output order
        return ", ".join(
            sorted(
                set(
                    [
                        block.fragment.collection.abbrev
                        for block in self.textblock_set.all()
                        if block.fragment.collection
                    ]
                )
            )
        )

    def all_languages(self):
        """comma delimited string of all primary languages for this document"""
        return ", ".join([str(lang) for lang in self.languages.all()])

    all_languages.short_description = "Language"

    def all_secondary_languages(self):
        """comma delimited string of all secondary languages for this document"""
        return ",".join([str(lang) for lang in self.secondary_languages.all()])

    all_secondary_languages.short_description = "Secondary Language"

    @cached_property
    def primary_lang_code(self):
        """Primary language code for this document, when there is only one
        primary language set and it has an ISO code available. Returns
        None if unset or unavailable.
        """
        # avoid using count() and first() so we don't hit the db for indexing
        if len(self.languages.all()) == 1:
            return self.languages.all()[0].iso_code or None

    @cached_property
    def primary_script(self):
        """Primary script for this document, if shared across all primary languages."""
        # aggregate all scripts for primary document languages
        # convert to set for uniqueness
        scripts = set([ls.script for ls in self.languages.all()])
        # if there is only one script, return it; otherwire return None
        if len(scripts) == 1:
            return list(scripts)[0]

    def all_tags(self):
        """comma delimited string of all tags for this document"""
        return ", ".join(t.name for t in self.tags.all())

    all_tags.short_description = "tags"

    def alphabetized_tags(self):
        """tags in alphabetical order, case-insensitive sorting"""
        return self.tags.order_by(Lower("name"))

    def is_public(self):
        """admin display field indicating if doc is public or suppressed"""
        return self.status == self.PUBLIC

    is_public.short_description = "Public"
    is_public.boolean = True
    is_public.admin_order_field = "status"

    def get_absolute_url(self):
        """url for this document"""
        return reverse("corpus:document", args=[str(self.id)])

    def iiif_urls(self):
        """List of IIIF urls for images of the Document's Fragments."""
        return list(
            dict.fromkeys(
                filter(None, [b.fragment.iiif_url for b in self.textblock_set.all()])
            )
        )

    def iiif_images(self, filter_side=False, with_placeholders=False):
        """
        Dict of IIIF images and labels for images of the Document's Fragments, keyed on canvas.


        :param filter_side: if TextBlocks have side info, filter images by side (default: False)
        :param with_placeholders: if there are digital editions with canvases missing images,
            include placeholder images for each additional canvas (default: False)"""
        iiif_images = {}
        textblocks = self.textblock_set.all()

        for b in textblocks:
            frag_images = b.fragment.iiif_images()
            if frag_images is not None:
                images, labels, canvases = frag_images
                for i, img in enumerate(images):
                    # include if filter inactive, no images selected, or this image is selected
                    if (
                        not filter_side
                        or not len(b.selected_images)
                        or i in b.selected_images
                    ):
                        iiif_images[canvases[i]] = {
                            "image": img,
                            "label": labels[i],
                            "canvas": canvases[i],
                            "shelfmark": b.fragment.shelfmark,
                            "rotation": 0,  # rotation to 0 by default; will change if overridden
                            "excluded": len(b.selected_images)
                            and i not in b.selected_images,
                        }

        # when requested, include any placeholder canvas URIs referenced by any associated
        # transcriptions or translations
        if with_placeholders:
            # get all distinct canvas URIs across all annotations on this document
            distinct_canvases = (
                Annotation.objects.filter(
                    footnote__content_type=ContentType.objects.get_for_model(Document),
                    footnote__object_id=self.pk,
                    content__target__source__id__isnull=False,
                )
                .order_by()
                .values_list("content__target__source__id", flat=True)
                .distinct()
            )
            # loop through each canvas in case we need to add any placeholders
            for canvas_uri in distinct_canvases:
                if canvas_uri not in iiif_images:
                    # use placeholder image for each canvas not in iiif_images
                    iiif_images[canvas_uri] = deepcopy(Document.PLACEHOLDER_CANVAS)
                    uri_match = re.search(
                        r"textblock\/(?P<tb_pk>\d+)\/canvas\/(?P<canvas>\d)\/",
                        canvas_uri,
                    )
                    if uri_match:
                        # if this was created using placeholders in the transcription editor,
                        # try to ascertain and display the right fragment shelfmark and label
                        tb_match_shelfmarks = [
                            tb.fragment.shelfmark
                            for tb in textblocks
                            if tb.pk == int(uri_match.group("tb_pk"))
                        ]
                        if tb_match_shelfmarks:
                            iiif_images[canvas_uri]["shelfmark"] = tb_match_shelfmarks[
                                0
                            ]
                        iiif_images[canvas_uri]["label"] = (
                            "recto" if int(uri_match.group("canvas")) == 1 else "verso"
                        )

        # if image_overrides not present, return list, in original order
        if not self.image_overrides:
            return iiif_images

        # sort canvases by "order" value
        sorted_overrides = sorted(
            self.image_overrides.items(),  # this will produce (canvas, overrides) tuples
            # get order if present; use ∞ as fallback to sort unordered to end of list
            key=lambda item: item[1].get("order", float("inf")),
        )
        # use that recreate dict keyed on canvas, but now in the overriden order
        ordered_images = {
            canvas: {
                # get values from original unordered dict
                **iiif_images.pop(canvas),
                # include rotation: overridden value or 0 degrees
                "rotation": int(override.get("rotation", 0)),
            }
            for canvas, override in sorted_overrides
            if canvas in iiif_images
        } or {}  # if condition is never met, instantiate empty dict (instead of set!)
        ordered_images.update(
            iiif_images  # add any remaining images after ordered ones
        )
        return ordered_images

    def list_thumbnail(self):
        """generate html for thumbnail of first image, for display in related documents lists"""
        iiif_images = self.iiif_images()
        if not iiif_images:
            return ""
        img = list(iiif_images.values())[0]
        return Fragment.admin_thumbnails(
            images=[
                img["image"]
                .size(height=60, width=60)
                .rotation(degrees=img["rotation"])
                .region(square=True)
            ],
            labels=[img["label"]],
            canvases=iiif_images.keys(),
        )

    def admin_thumbnails(self):
        """generate html for thumbnails of all iiif images, for image reordering UI in admin"""
        iiif_images = self.iiif_images()
        if not iiif_images:
            return ""
        return Fragment.admin_thumbnails(
            images=[
                img["image"].size(height=200).rotation(degrees=img["rotation"])
                for img in iiif_images.values()
            ],
            labels=[img["label"] for img in iiif_images.values()],
            canvases=iiif_images.keys(),
        )

    admin_thumbnails.short_description = "Image order/rotation overrides"

    def fragment_urls(self):
        """List of external URLs to view the Document's Fragments."""
        return list(
            dict.fromkeys(
                filter(None, [b.fragment.url for b in self.textblock_set.all()])
            )
        )

    def fragments_other_docs(self):
        """List of other documents that are on the same fragment(s) as this
        document (does not include suppressed documents). Returns a list of
        :class:`~corpus.models.Document` objects."""
        # get the set of all documents from all fragments, remove current document,
        # then convert back to a list
        return list(
            set(
                [
                    doc
                    for frag in self.fragments.all()
                    for doc in frag.documents.filter(status=Document.PUBLIC)
                ]
            )
            - {self}
        )

    @cached_property
    def related_documents(self):
        """List of other documents with any of the same shelfmarks as this
        document; does not include suppressed documents. Queries Solr and
        returns a list of :class:`dict` objects."""
        return DocumentSolrQuerySet().related_to(self)

    def has_transcription(self):
        """Admin display field indicating if document has a transcription."""
        # avoids an additional DB call for admin list view
        return any(
            [
                Footnote.DIGITAL_EDITION in note.doc_relation
                for note in self.footnotes.all()
            ]
        )

    has_transcription.short_description = "Transcription"
    has_transcription.boolean = True

    def has_translation(self):
        """Helper method to determine if document has a translation.

        :return: Whether document has translation
        :rtype: bool
        """
        return any(
            [
                Footnote.DIGITAL_TRANSLATION in note.doc_relation
                for note in self.footnotes.all()
            ]
        )

    has_translation.short_description = "Translation"
    has_translation.boolean = True

    def has_image(self):
        """Admin display field indicating if document has a IIIF image."""
        return any(self.iiif_urls())

    has_image.short_description = "Image"
    has_image.boolean = True
    has_image.admin_order_field = "textblock__fragment__iiif_url"

    def has_digital_content(self):
        """Helper method for the ITT viewer on the public front-end to determine whether a document
        has any images, digital editions, or digital translations."""
        return any(
            [
                self.has_image(),
                any(
                    [
                        Footnote.DIGITAL_EDITION in note.doc_relation
                        or Footnote.DIGITAL_TRANSLATION in note.doc_relation
                        for note in self.footnotes.all()
                    ]
                ),
            ]
        )

    @property
    def available_digital_content(self):
        """Helper method for the ITT viewer to collect all available panels into a list"""

        # NOTE: this is ordered by priority, with images first, then translations over
        # transcriptions.
        available_panels = []
        if self.has_image():
            available_panels.append("images")
        if self.has_translation():
            available_panels.append("translation")
        if self.has_transcription():
            available_panels.append("transcription")
        return available_panels

    @property
    def title(self):
        """Short title for identifying the document, e.g. via search."""
        return f"{self.doctype or _('Unknown type')}: {self.shelfmark_display or '??'}"

    def dating_range(self):
        """
        Return the start and end of the document's possible date range, as PartialDate objects,
        including standardized document dates and inferred Datings, if any exist.
        """
        # it is unlikely, but technically possible, that a document could have both on-document
        # dates and inferred datings, so find the min and max out of all of them.

        # start_date and end_date are PartialDate instances
        dating_range = [self.start_date or None, self.end_date or None]

        # bail out if we don't have any inferred datings
        if not self.dating_set.exists():
            return tuple(dating_range)

        # loop through inferred datings to find min and max among all dates (including both
        # on-document and inferred)
        for inferred in self.dating_set.all():
            # get start from standardized date range (formatted as "date1/date2" or "date")
            split_date = inferred.standard_date.split("/")
            start = PartialDate(split_date[0])
            # get end from standardized date range
            end = PartialDate(split_date[1]) if len(split_date) > 1 else start
            dating_range = PartialDate.get_date_range(
                old_range=dating_range, new_range=[start, end]
            )

        return tuple(dating_range)

    def solr_dating_range(self):
        """Return the document's dating range, including inferred, as a Solr date range."""
        solr_dating_range = []
        # self.dating_range() should always return a tuple of two values
        for i, date in enumerate(self.dating_range()):
            if date:
                # min/max from dating_range, formatted YYYY-MM-DD or YYYY-MM or YYYY
                solr_dating_range.append(
                    date.isoformat(mode="max" if i == 1 else "min")
                )
        if not solr_dating_range:
            return None
        # if a single date instead of a range, just return that date
        if solr_dating_range[0] == solr_dating_range[1]:
            return solr_dating_range[0]
        # if there's more than one date, return as a range
        return "[%s TO %s]" % tuple(solr_dating_range)

    def editions(self):
        """All footnotes for this document where the document relation includes
        edition."""
        return self.footnotes.filter(doc_relation__contains=Footnote.EDITION).order_by(
            "source"
        )

    def digital_editions(self):
        """All footnotes for this document where the document relation includes
        digital edition."""

        return self.footnotes.filter(
            doc_relation__contains=Footnote.DIGITAL_EDITION
        ).order_by("source")

    def editors(self):
        """All unique authors of digital editions for this document."""
        return Creator.objects.filter(
            source__footnote__doc_relation__contains=Footnote.DIGITAL_EDITION,
            source__footnote__document=self,
        ).distinct()

    def digital_translations(self):
        """All footnotes for this document where the document relation includes
        digital translation."""

        return self.footnotes.filter(
            doc_relation__contains=Footnote.DIGITAL_TRANSLATION
        ).order_by("source")

    @property
    def default_translation(self):
        """The first translation footnote that is in the current language, or the first
        translation footnote ordered alphabetically by source if one is not available
        in the current language."""

        translations = self.digital_translations()
        in_language = translations.filter(source__languages__code=get_language())
        return in_language.first() or translations.first()

    def digital_footnotes(self):
        """All footnotes for this document where the document relation includes
        digital edition or digital translation."""

        return self.footnotes.filter(
            models.Q(doc_relation__contains=Footnote.DIGITAL_EDITION)
            | models.Q(doc_relation__contains=Footnote.DIGITAL_TRANSLATION)
        ).distinct()

    def sources(self):
        """All unique sources attached to footnotes on this document."""
        # use set and local references to avoid an extra db call
        return set([fn.source for fn in self.footnotes.all()])
        # return Source.objects.filter(footnote__document=self).distinct()

    def attribution(self):
        """Generate a tuple of three attribution components for use in IIIF manifests
        or wherever images/transcriptions need attribution."""

        # NOTE: For individual fragment attribution, use :class:`Fragment` method instead.

        # keep track of unique attributions so we can include them all
        extra_attrs_set = set()
        for url in self.iiif_urls():
            # NOTE: If this url fails, may raise IIIFException
            remote_manifest = IIIFPresentation.from_url(url)
            # CUDL attribution has some variation in tags;
            # would be nice to preserve tagged version,
            # for now, ignore tags so we can easily de-dupe
            try:
                extra_attrs_set.add(strip_tags(remote_manifest.attribution))
            except AttributeError:
                # attribution is optional, so ignore if not present
                pass
        pgp = _("Princeton Geniza Project")
        # Translators: attribution for local IIIF manifests
        attribution = _("Compilation by %(pgp)s." % {"pgp": pgp})
        if self.has_transcription():
            # Translators: attribution for local IIIF manifests that include transcription
            attribution = _("Compilation and transcription by %(pgp)s." % {"pgp": pgp})
        # Translators: manifest attribution note that content from other institutions may have restrictions
        additional_restrictions = _("Additional restrictions may apply.")

        return (
            attribution,
            additional_restrictions,
            extra_attrs_set,
        )

    @classmethod
    def total_to_index(cls):
        """static method to efficiently count the number of documents to index in Solr"""
        # quick count for parasolr indexing (don't do prefetching just to get the total!)
        return cls.objects.count()

    @classmethod
    def items_to_index(cls):
        """Custom logic for finding items to be indexed when indexing in
        bulk."""
        return Document.objects.prefetch_related(
            "tags",
            "languages",
            "secondary_languages",
            "log_entries",
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment", "fragment__collection", "fragment__manifest"
                ).prefetch_related("fragment__manifest__canvases"),
            ),
            Prefetch(
                "footnotes",
                queryset=Footnote.objects.select_related(
                    "source", "source__source_type"
                ).prefetch_related(
                    "source__authorship_set",
                    "source__authorship_set__creator",
                    "source__languages",
                    "annotation_set",
                ),
            ),
        )

    @classmethod
    def prep_index_chunk(cls, chunk):
        """Prefetch related information when indexing in chunks
        (modifies queryset chunk in place)"""
        models.prefetch_related_objects(
            chunk,
            "doctype",
            "tags",
            "languages",
            "log_entries",
            "dating_set",
            "persondocumentrelation_set",
            "documentplacerelation_set",
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment", "fragment__collection", "fragment__manifest"
                ).prefetch_related("fragment__manifest__canvases"),
            ),
            Prefetch(
                "footnotes",
                queryset=Footnote.objects.select_related(
                    "source", "source__source_type"
                ).prefetch_related(
                    "source__authorship_set",
                    "source__authorship_set__creator",
                    "source__languages",
                    "annotation_set",
                ),
            ),
        )
        return chunk

    def index_data(self):
        """data for indexing in Solr"""
        index_data = super().index_data()

        # get fragments via textblocks for correct order
        # and to take advantage of prefetching
        fragments = [tb.fragment for tb in self.textblock_set.all()]
        # filter by side so that search results only show the relevant side image(s)
        images = self.iiif_images(filter_side=True).values()
        index_data.update(
            {
                "pgpid_i": self.id,
                # type gets matched back to DocumentType object in get_result_document, for i18n;
                # should always be indexed in English
                "type_s": (
                    (
                        self.doctype.display_label_en
                        or self.doctype.name_en
                        or str(self.doctype)
                    )
                    if self.doctype
                    else "Unknown type"
                ),
                # use english description for now
                "description_en_bigram": strip_tags(self.description_en),
                "notes_t": self.notes or None,
                "needs_review_t": self.needs_review or None,
                # index shelfmark label as a string (combined shelfmark OR shelfmark override)
                "shelfmark_s": self.shelfmark_display,
                # index individual shelfmarks for search (includes uncertain fragments)
                "fragment_shelfmark_ss": [f.shelfmark for f in fragments],
                # index any old/historic shelfmarks as a list
                # split multiple shelfmarks on any one fragment into a list;
                # flatten the lists into a single list
                "fragment_old_shelfmark_ss": list(
                    chain(*[f.old_shelfmarks.split("; ") for f in fragments])
                ),
                # combined original/standard document date for display
                "document_date_t": strip_tags(self.document_date) or None,
                # date range for filtering
                "document_date_dr": self.solr_date_range(),
                # date range for filtering, but including inferred datings if any exist
                "document_dating_dr": self.solr_dating_range(),
                # historic date, for searching
                # start/end of document date or date range
                "start_date_i": (
                    self.start_date.numeric_format() if self.start_date else None
                ),
                "end_date_i": (
                    self.end_date.numeric_format(mode="max") if self.end_date else None
                ),
                # library/collection possibly redundant?
                "collection_ss": [str(f.collection) for f in fragments],
                "tags_ss_lower": [t.name for t in self.tags.all()],
                "status_s": self.get_status_display(),
                "old_pgpids_is": self.old_pgpids,
                "language_code_s": self.primary_lang_code,
                "language_script_s": self.primary_script,
                "language_name_ss": [str(l) for l in self.languages.all()],
                # use image info link without trailing info.json to easily convert back to iiif image client
                # NOTE: if/when piffle supports initializing from full image uris, we could simplify this
                # code to index the full image url, with rotation overrides applied
                "iiif_images_ss": [
                    img["image"].info()[:-10]  # i.e., remove /info.json
                    for img in images
                ],
                "iiif_labels_ss": [img["label"] for img in images],
                "iiif_rotations_is": [img["rotation"] for img in images],
                "has_image_b": len(images) > 0,
                "people_count_i": self.persondocumentrelation_set.count(),
                "places_count_i": self.documentplacerelation_set.count(),
            }
        )

        # count scholarship records by type
        footnotes = self.footnotes.all()
        counts = defaultdict(int)
        # collect transcription and translation texts for indexing
        transcription_texts = []
        transcription_texts_regex = []
        translation_texts = []
        # keep track of translation language for RTL/LTR display
        translation_langcode = ""
        translation_langdir = "ltr"

        # dict of sets of relations; keys are each source attached to any footnote on this document
        source_relations = defaultdict(set)

        for fn in footnotes:
            # if this is an edition/transcription, get html version for indexing
            if Footnote.DIGITAL_EDITION in fn.doc_relation:
                content = fn.content_html_str
                if content:
                    transcription_texts.append(Footnote.explicit_line_numbers(content))
                    for canvas in fn.content_text_canvases:
                        # index plaintext only for regex
                        transcription_texts_regex.append(canvas)
            elif Footnote.DIGITAL_TRANSLATION in fn.doc_relation:
                content = fn.content_html_str
                if content:
                    translation_texts.append(Footnote.explicit_line_numbers(content))
                    # TODO: Index translations in different languages separately
                    if fn.source.languages.exists():
                        lang = fn.source.languages.first()
                        translation_langcode = lang.code
                        translation_langdir = lang.direction
            # add any doc relations to this footnote's source's set in source_relations
            source_relations[fn.source] = source_relations[fn.source].union(
                fn.doc_relation
            )

        # make sure digital editions/translations are also counted,
        # whether or not there is a separate edition/translation footnote
        for source, doc_relations in source_relations.items():
            if Footnote.DIGITAL_EDITION in doc_relations:
                source_relations[source].add(Footnote.EDITION)
            if Footnote.DIGITAL_TRANSLATION in doc_relations:
                source_relations[source].add(Footnote.TRANSLATION)

        # flatten sets of relations by source into a list of relations
        for relation in list(chain(*source_relations.values())):
            # add one for each relation in the flattened list
            counts[relation] += 1

        index_data.update(
            {
                "num_editions_i": counts[Footnote.EDITION],
                "num_translations_i": counts[Footnote.TRANSLATION],
                "num_discussions_i": counts[Footnote.DISCUSSION],
                # count each unique source as one scholarship record
                "scholarship_count_i": len(source_relations.keys()),
                # preliminary scholarship record indexing
                # (may need splitting out and weighting based on type of scholarship)
                "scholarship_t": [fn.display() for fn in footnotes],
                # transcription content as html
                "text_transcription": transcription_texts,
                "transcription_regex": transcription_texts_regex,
                "translation_language_code_s": translation_langcode,
                "translation_language_direction_s": translation_langdir,
                # translation content as html
                "text_translation": translation_texts,
                "has_digital_edition_b": bool(counts[Footnote.DIGITAL_EDITION]),
                "has_digital_translation_b": bool(counts[Footnote.DIGITAL_TRANSLATION]),
                "has_discussion_b": bool(counts[Footnote.DISCUSSION]),
            }
        )

        # convert to list so we can do negative indexing, instead of calling last()
        # which incurs a database call
        try:
            last_log_entry = list(self.log_entries.all())[-1]
        except IndexError:
            # occurs in unit tests, and sometimes when new documents are indexed before
            # log entry is populated
            last_log_entry = None

        if last_log_entry:
            index_data["input_year_i"] = last_log_entry.action_time.year
            # TODO: would be nice to use full date to display year
            # instead of indexing separately
            # (may require parasolr datetime conversion support? or implement
            # in local queryset?)
            index_data[
                "input_date_dt"
            ] = last_log_entry.action_time.isoformat().replace("+00:00", "Z")
        elif self.created:
            # when log entry not available, use created date on document object
            # (will always exist except in some unit tests)
            index_data["input_year_i"] = self.created.year
            index_data["input_date_dt"] = self.created.isoformat().replace(
                "+00:00", "Z"
            )

        return index_data

    # define signal handlers to update the index based on changes
    # to other models
    index_depends_on = {
        "fragments": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "tags": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "doctype": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "textblock_set": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "footnotes.footnote": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "footnotes.source": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "footnotes.creator": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "annotations.annotation": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
    }

    @cached_property
    def manifest_uri(self):
        # manifest uri for the current document
        return "%s%s" % (
            settings.ANNOTATION_MANIFEST_BASE_URL,
            reverse("corpus-uris:document-manifest", args=[self.pk]),
        )

    def merge_with(self, merge_docs, rationale, user=None):
        """Merge the specified documents into this one. Combines all
        metadata into this document, adds the merged documents into
        list of old PGP IDs, and creates a log entry documenting
        the merge, including the rationale."""

        # if user is not specified, log entry will be associated with
        # script and document will be flagged for review
        script = False
        if user is None:
            user = User.objects.get(username=settings.SCRIPT_USERNAME)
            script = True

        # language codes are needed to merge description, which is translated
        language_codes = [lang_code for lang_code, lang_name in settings.LANGUAGES]

        # handle translated description: create a dict of descriptions
        # per supported language to aggregate and merge
        description_chunks = {
            lang_code: [getattr(self, "description_%s" % lang_code) or ""]
            for lang_code in language_codes
        }
        language_notes = [self.language_note] if self.language_note else []
        notes = [self.notes] if self.notes else []
        needs_review = [self.needs_review] if self.needs_review else []

        for doc in merge_docs:
            # handle document dates validation before making any changes;
            # mismatch should result in exception (caught by DocumentMerge.form_valid)
            if (
                (
                    # both documents have standard dates, and they don't match
                    doc.doc_date_standard
                    and self.doc_date_standard
                    and self.doc_date_standard != doc.doc_date_standard
                )
                or (
                    # both documents have original dates, and they don't match
                    doc.doc_date_original
                    and self.doc_date_original
                    and self.doc_date_original != doc.doc_date_original
                )
                or (
                    # other document has original, this doc has standard, and they don't match
                    doc.doc_date_original
                    and self.doc_date_standard
                    and doc.standardize_date() != self.doc_date_standard
                )
                or (
                    # other document has standard, this doc has original, and they don't match
                    doc.doc_date_standard
                    and self.doc_date_original
                    and self.standardize_date() != doc.doc_date_standard
                )
            ):
                raise ValidationError(
                    "Merged documents must not contain conflicting dates; resolve before merge"
                )

            # add any tags from merge document tags to primary doc
            self.tags.add(*doc.tags.names())

            # if not in conflict (i.e. missing or exact duplicate), copy dates to result document
            if doc.doc_date_standard:
                self.doc_date_standard = doc.doc_date_standard
            if doc.doc_date_original:
                self.doc_date_original = doc.doc_date_original
                self.doc_date_calendar = doc.doc_date_calendar

            # add inferred datings (conflicts or duplicates are post-merge
            # data cleanup tasks)
            for dating in doc.dating_set.all():
                self.dating_set.add(dating)

            # initialize old pgpid list if previously unset
            if self.old_pgpids is None:
                self.old_pgpids = []
            # add merge id to old pgpid list
            self.old_pgpids.append(doc.id)
            # add description if set and not duplicated
            # for all supported languages
            for lang_code in language_codes:
                description_field = "description_%s" % lang_code
                doc_description = getattr(doc, description_field)
                current_description = getattr(self, description_field) or ""
                if doc_description and doc_description not in current_description:
                    description_chunks[lang_code].append(
                        "Description from PGPID %s:\n%s" % (doc.id, doc_description)
                    )
            # add any notes
            if doc.notes:
                notes.append("Notes from PGPID %s:\n%s" % (doc.id, doc.notes))
            if doc.needs_review:
                needs_review.append(doc.needs_review)

            # add languages and secondary languages
            for lang in doc.languages.all():
                self.languages.add(lang)
            for lang in doc.secondary_languages.all():
                self.secondary_languages.add(lang)
            if doc.language_note:
                language_notes.append(doc.language_note)

            # if there are any textblocks with fragments not already
            # asociated with this document, reassociate
            # (i.e., for newly discovered joins)
            # does not deal with discrepancies between text block fields or order
            for textblock in doc.textblock_set.all():
                if textblock.fragment not in self.fragments.all():
                    self.textblock_set.add(textblock)

            self._merge_footnotes(doc)
            self._merge_logentries(doc)

        # combine aggregated content for text fields
        for lang_code in language_codes:
            description_field = "description_%s" % lang_code
            # combine, but filter out any None values from unset content
            setattr(
                self,
                description_field,
                "\n".join([d for d in description_chunks[lang_code] if d]),
            )

        self.notes = "\n".join(notes)
        self.language_note = "; ".join(language_notes)
        # if merged via script, flag for review
        if script:
            needs_review.insert(0, "SCRIPTMERGE")
        self.needs_review = "\n".join(needs_review)

        # save current document with changes; delete merged documents
        self.save()
        merged_ids = ", ".join([str(doc.id) for doc in merge_docs])
        for doc in merge_docs:
            doc.delete()
        # create log entry documenting the merge; include rationale
        doc_contenttype = ContentType.objects.get_for_model(Document)
        LogEntry.objects.log_action(
            user_id=user.id,
            content_type_id=doc_contenttype.pk,
            object_id=self.pk,
            object_repr=str(self),
            change_message="merged with %s: %s" % (merged_ids, rationale),
            action_flag=CHANGE,
        )

    def _merge_footnotes(self, doc):
        # combine footnotes; footnote logic for merge_with
        for footnote in doc.footnotes.all():
            # check for match. for each pair of footnotes, there are two possible cases for
            # non-equivalence:
            # - the footnote to be merged in has annotations
            # - there are fields on the footnotes that don't match
            # in the former case, merge the two by migrating the annotations from the footnote to
            # be merged in to an otherwise matching footnote if there is one; else, add it to doc.
            # in the latter case, simply add the footnote to this document.

            if footnote.annotation_set.exists():
                try:
                    # if the footnote to be merged in has annotations, try to reassign them to an
                    # otherwise matching footnote to avoid unique constraint violation
                    self_fn = self.footnotes.get(
                        # for multiselect field list, need to cast to list to compare
                        doc_relation__in=list(footnote.doc_relation),
                        source_id=footnote.source.pk,
                    )
                    # copy over notes, location, url if missing from self_fn
                    for attr in ["notes", "location", "url"]:
                        if not getattr(self_fn, attr) and getattr(footnote, attr):
                            setattr(self_fn, attr, getattr(footnote, attr))
                    self_fn.save()
                    # reassign each annotation's footnote to the footnote on this doc
                    for annotation in footnote.annotation_set.all():
                        annotation.footnote = self_fn
                        annotation.save()
                except Footnote.DoesNotExist:
                    # if there is no match, we are clear of any unique constaint violation and can
                    # simply add the footnote to this document
                    self.footnotes.add(footnote)
            elif not self.footnotes.includes_footnote(footnote):
                # if there is otherwise not a match, add the footnote to this document

                # first remove any digital doc relations to avoid unique constraint violation;
                # footnote should not have such a relation anyway if there are 0 annotations, so
                # this would be a data error.
                if Footnote.DIGITAL_EDITION in footnote.doc_relation:
                    footnote.doc_relation.remove(Footnote.DIGITAL_EDITION)
                    footnote.save()
                if Footnote.DIGITAL_TRANSLATION in footnote.doc_relation:
                    footnote.doc_relation.remove(Footnote.DIGITAL_TRANSLATION)
                    footnote.save()

                # then add to this document
                self.footnotes.add(footnote)

    def _merge_logentries(self, doc):
        # reassociate log entries; logic for merge_with
        # make a list of currently associated log entries to skip duplicates
        current_logs = [
            "%s_%s" % (le.user_id, le.action_time.isoformat())
            for le in self.log_entries.all()
        ]
        for log_entry in doc.log_entries.all():
            # check duplicate log entries, based on user id and time
            # (likely only applies to historic input & revision)
            if (
                "%s_%s" % (log_entry.user_id, log_entry.action_time.isoformat())
                in current_logs
            ):
                # skip if it's a duplicate
                continue

            # otherwise annotate and reassociate
            # - modify change message to document which object this event applied to
            log_entry.change_message = "%s [PGPID %d]" % (
                log_entry.change_message,
                doc.pk,
            )

            # - associate with the primary document
            log_entry.object_id = self.id
            log_entry.content_type_id = ContentType.objects.get_for_model(Document)
            log_entry.save()


@receiver(pre_delete, sender=Document)
def detach_document_logentries(sender, instance, **kwargs):
    """:class:`~Document` pre-delete signal handler.

    To avoid deleting log entries caused by the generic relation
    from document to log entries, clear out object id
    for associated log entries before deleting the document."""
    instance.log_entries.update(object_id=None)


class TextBlock(models.Model):
    """The portion of a document that appears on a particular fragment."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    fragment = models.ForeignKey(Fragment, on_delete=models.CASCADE)
    certain = models.BooleanField(
        default=True,
        help_text=(
            "Are you certain that this fragment belongs to this document? "
            + "Uncheck this box if you are uncertain of a potential join."
        ),
    )
    RECTO = "recto"
    VERSO = "verso"
    RECTO_VERSO = "recto and verso"
    selected_images = ArrayField(
        models.IntegerField(),
        default=list,
        blank=True,
        verbose_name="Selected image indices",
    )
    region = models.CharField(
        blank=True,
        max_length=255,
        help_text="Label for region of fragment that document text occupies",
    )
    multifragment = models.CharField(
        max_length=255,
        blank=True,
        help_text="Identifier for fragment part, if part of a multifragment",
    )
    order = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Order with respect to other text blocks in this document, "
        + "top to bottom or right to left",
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "Related Fragment"  # for researcher legibility in admin

    def __str__(self):
        # combine shelfmark, multifragment, side, region, and certainty
        certainty_str = "(?)" if not self.certain else ""
        parts = [
            self.fragment.shelfmark,
            self.multifragment,
            self.side,
            self.region,
            certainty_str,
        ]
        return " ".join(p for p in parts if p)

    @property
    def side(self):
        """Recto/verso side information based on selected image indices"""
        if len(self.selected_images) == 1:
            if self.selected_images[0] == 0:
                return self.RECTO
            elif self.selected_images[0] == 1:
                return self.VERSO
        elif len(self.selected_images) == 2 and all(
            i in self.selected_images for i in [0, 1]
        ):
            return self.RECTO_VERSO
        return ""

    def thumbnail(self):
        """iiif thumbnails for this TextBlock, with selected images highlighted"""
        return self.fragment.iiif_thumbnails(selected=self.selected_images)


class Dating(models.Model):
    """An inferred date for a document."""

    class Meta:
        verbose_name_plural = "Inferred datings (not written on the document)"

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, null=False, blank=False
    )
    display_date = models.CharField(
        "Display date",
        help_text='The dating as it should appear in the public site, such as "Late 12th century"',
        max_length=255,
        blank=True,  # use standard date for display if this is blank
    )
    standard_date = models.CharField(
        "CE date",
        help_text=DocumentDateMixin.standard_date_helptext,
        blank=False,
        null=False,
        max_length=255,
        validators=[RegexValidator(DocumentDateMixin.re_date_format)],
    )
    PALEOGRAPHY = "PA"
    PALEOGRAPHY_LABEL = "Paleography"
    PERSON = "PE"
    PERSON_LABEL = "Person mentioned"
    EVENT = "E"
    EVENT_LABEL = "Event mentioned"
    COINAGE = "C"
    COINAGE_LABEL = "Coinage"
    OTHER = "O"
    OTHER_LABEL = "Other (please specify)"
    RATIONALE_CHOICES = (
        (PALEOGRAPHY, PALEOGRAPHY_LABEL),
        (PERSON, PERSON_LABEL),
        (EVENT, EVENT_LABEL),
        (COINAGE, COINAGE_LABEL),
        (OTHER, OTHER_LABEL),
    )
    rationale = models.CharField(
        max_length=2,
        choices=RATIONALE_CHOICES,
        default=OTHER,
        help_text="An explanation for how this date was inferred",
        blank=False,
        null=False,
    )
    notes = models.TextField(
        help_text="Optional further details about the rationale",
    )

    @property
    def standard_date_display(self):
        """Standard date in human-readable format for document details pages"""
        return standard_date_display(self.standard_date)


class DocumentEventRelation(models.Model):
    """A relationship between a document and an event"""

    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    event = models.ForeignKey("entities.Event", on_delete=models.CASCADE)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Document-Event relation: {self.document} and {self.event}"

import logging
import re
from datetime import datetime
from math import modf
from operator import itemgetter

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import F, Q, Value
from django.db.models.query import Prefetch
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.forms import ValidationError
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from gfklookupwidget.fields import GfkLookupField
from parasolr.django import AliasedSolrQuerySet
from parasolr.django.indexing import ModelIndexable
from slugify import slugify
from taggit.managers import TaggableManager
from unidecode import unidecode

from geniza.common.models import TaggableMixin, TrackChangesModel, cached_class_property
from geniza.common.signals import detach_logentries
from geniza.corpus.dates import DocumentDateMixin, PartialDate, standard_date_display
from geniza.corpus.models import (
    Dating,
    DisplayLabelMixin,
    Document,
    LanguageScript,
    PermalinkMixin,
)
from geniza.footnotes.models import Footnote

logger = logging.getLogger(__name__)


class NameQuerySet(models.QuerySet):
    """Custom queryset for names for filter utility functions"""

    def non_primary(self):
        """Filter this queryset to only non-primary names"""
        return self.filter(primary=False)


class Name(models.Model):
    """A name for an entity, such as a person or a place."""

    name = models.CharField(
        max_length=255,
        help_text="Please add common forms of the name in both English and other languages in which it appears in documents.",
    )
    primary = models.BooleanField(
        default=False,
        help_text="Check box if this is the primary name that should be displayed on the site.",
        verbose_name="Display name",
    )
    language = models.ForeignKey(
        LanguageScript,
        on_delete=models.SET_NULL,
        null=True,
        help_text='Please indicate the language of most components of the name as written here. Refers to the language in which a name is written, not the linguistic origin of the name. Ex: “Nahray b. Nissim” and "Fusṭāṭ" should be marked as English.',
    )
    notes = models.TextField(blank=True)

    # Generic relationship with named entities
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="entities"),
    )
    object_id = GfkLookupField("content_type")
    content_object = GenericForeignKey()

    # use custom manager & queryset
    objects = NameQuerySet.as_manager()

    # transliteration style
    PGP = "P"
    CAMBRIDGE = "C"
    NONE = "N"
    TRANSLITERATION_CHOICES = (
        (NONE, "N/A"),
        (PGP, "PGP"),
        (CAMBRIDGE, "Cambridge"),
    )
    transliteration_style = models.CharField(
        max_length=1,
        choices=TRANSLITERATION_CHOICES,
        default=NONE,
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Override of the model save method to cleanup unicode non breaking space character"""
        self.name = re.sub(r"[\xa0 ]+", " ", self.name)
        super().save(*args, **kwargs)


class DocumentDatableMixin:
    """Mixin for entities that have associated documents, and thus can be automatically
    roughly dated by the dates on those documents."""

    @property
    def documents_date_range(self):
        """Compute the total range of dates across all associated documents"""
        return self.get_date_range(self.documents.all())

    def get_date_range(self, doc_set):
        """Standardized range of dates across a set of documents"""
        full_range = [None, None]
        for doc in doc_set:
            # get each doc's full range, including inferred and on-document
            doc_range = doc.dating_range()
            # if doc has a range, and the range is not [None, None], compare
            # it against the current min and max
            if doc_range and doc_range[0]:
                start = doc_range[0]
                end = doc_range[1] if len(doc_range) > 1 else start
                # update full range with comparison results
                full_range = PartialDate.get_date_range(
                    old_range=full_range, new_range=[start, end]
                )
        # prune Nones and use isoformat for standardized representation
        full_range = [d.isoformat() for d in full_range if d]
        if len(full_range) == 2 and full_range[0] == full_range[1]:
            full_range.pop(1)
        return "/".join(full_range)


class Event(DocumentDatableMixin, models.Model):
    """A historical event involving one or more documents, and optionally additional entities."""

    name = models.CharField(
        max_length=255,
        help_text="A short name for the event to use as a display label",
    )
    description = models.TextField(
        blank=True,
        help_text="A description of the event",
    )
    footnotes = GenericRelation(Footnote, blank=True, related_query_name="event")
    display_date = models.CharField(
        "Display date",
        help_text='''Display date for manually entered or automatically generated date,
        as it should appear in the public site, such as "Late 12th century"''',
        max_length=255,
        blank=True,  # use standard date for display if this is blank
    )
    standard_date = models.CharField(
        "CE date override",
        help_text="Manual override for automatically generated date or date range. "
        + DocumentDateMixin.standard_date_helptext,
        blank=True,  # use automatic date range from associated documents if this is blank
        null=True,
        max_length=255,
        validators=[RegexValidator(DocumentDateMixin.re_date_format)],
    )

    def __str__(self):
        """Use the name field for string representations"""
        return self.name

    @property
    def date_str(self):
        """Return a formatted string for the event's date/range, for use in public site.
        Display date override takes highest precedence; fallback to formatted CE date override,
        then computed date range from associated documents if neither override is set.
        """
        return (
            self.display_date
            or standard_date_display(self.standard_date)
            or standard_date_display(self.documents_date_range)
        )


class PersonRoleManager(models.Manager):
    """Custom manager for :class:`PersonRole` with natural key lookup"""

    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class PersonRole(DisplayLabelMixin, models.Model):
    """Controlled vocabulary of person roles."""

    name = models.CharField(max_length=255, unique=True)
    display_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional label for display on the public site",
    )
    objects = PersonRoleManager()

    @cached_class_property
    def objects_by_label(cls):
        return super().objects_by_label()

    def __str__(self):
        return self.display_label or self.name

    class Meta:
        verbose_name = "Person social role"
        verbose_name_plural = "Person social roles"
        ordering = ["display_label", "name"]


class SlugMixin(TrackChangesModel):
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text="Short, durable, unique identifier for use in URLs. "
        + "Save and continue editing to have a new slug autogenerated. "
        + "Editing will change the public, citable URL for this entity.",
    )
    # NOTE: null=true required to avoid validation error
    # when submitting admin edit form with no slug

    def generate_slug(self):
        """Generate a slug for this entity based on primary name and ensure it is unique.
        Adapted from mep-django."""
        self.slug = self.dedupe_slug(slugify(unidecode(str(self))))

    def dedupe_slug(self, slug):
        """Ensure slug is unique"""
        dupe_slugs = (
            self.__class__.objects.filter(slug__startswith=slug)
            .exclude(pk=self.pk)
            .order_by("slug")
            .values_list("slug", flat=True)
        )
        if dupe_slugs.count() and slug in dupe_slugs:
            # if not unique, add a number
            prefix = "%s-" % slug
            # get all the endings attached to this slug (i.e. unclear-##)
            suffixes = [s[len(prefix) :] for s in dupe_slugs if s.startswith(prefix)]
            # get the largest numeric suffix
            values = [int(num) for num in suffixes if num.isnumeric()]
            slug_count = max(values) if values else 1
            # use the next number for the current slug
            slug = "%s-%s" % (slug, slug_count + 1)
        return slug

    class Meta:
        abstract = True


class PersonSignalHandlers:
    """Signal handlers for indexing :class:`Person` records when
    related records are saved or deleted."""

    # lookup from model verbose name to attribute on person
    # for use in queryset filter
    model_filter = {
        "name": "names",
        "Person social role": "roles",
        "document": "documents",  # documents in case dates change
        "person person relation": ["to_person", "from_person"],
        "person place relation": "personplacerelation",
        "person document relation": "persondocumentrelation",
        "Person-Document relationship": "persondocumentrelation__type",  # relation type
    }

    @staticmethod
    def related_change(instance, raw, mode):
        """reindex all associated people when related data is changed"""
        # common logic for save and delete
        # raw = saved as presented; don't query the database
        if raw or not instance.pk:
            return
        # get related lookup for person filter
        model_name = instance._meta.verbose_name
        person_attr = PersonSignalHandlers.model_filter.get(model_name)
        # if handler fired on an model we don't care about, warn and exit
        if not person_attr:
            logger.warning(
                "Indexing triggered on %s but no person attribute is configured"
                % model_name
            )
            return

        # handle cases where there is more than one matching attr; for now this is only
        # for person-person (self-referential), but maybe could be used for other things
        if isinstance(person_attr, list):
            person_filter = Q()
            for attr in person_attr:
                condition = {"%s__pk" % attr: instance.pk}
                person_filter |= Q(**condition)
            people = Person.items_to_index().filter(person_filter)
        else:
            person_filter = {"%s__pk" % person_attr: instance.pk}
            people = Person.items_to_index().filter(**person_filter)
        if people.exists():
            logger.debug(
                "%s %s, reindexing %d related person(s)",
                model_name,
                mode,
                people.count(),
            )
            ModelIndexable.index_items(people)

    @staticmethod
    def related_save(sender, instance=None, raw=False, **_kwargs):
        """reindex associated people when a related object is saved"""
        # delegate to common method
        PersonSignalHandlers.related_change(instance, raw, "save")

    @staticmethod
    def related_delete(sender, instance=None, raw=False, **_kwargs):
        """reindex associated people when a related object is deleted"""
        # delegate to common method
        PersonSignalHandlers.related_change(instance, raw, "delete")


class Person(
    ModelIndexable, SlugMixin, DocumentDatableMixin, PermalinkMixin, TaggableMixin
):
    """A person entity that appears within the PGP corpus."""

    names = GenericRelation(Name, related_query_name="person")
    description = models.TextField(
        blank=True,
        help_text="A description that will appear on the public Person page if 'Person page' box is checked.",
    )
    has_page = models.BooleanField(
        help_text="Check box if this person should have a dedicated, public Person page on the PGP. If checked, please draft a public description below.",
        default=False,
        verbose_name="Person page",
    )
    documents = models.ManyToManyField(
        Document,
        related_name="people",
        through="PersonDocumentRelation",
        verbose_name="Related Documents",
    )
    relationships = models.ManyToManyField(
        "self",
        related_name="related_to",
        # asymmetrical because the reverse relation would have a different type
        symmetrical=False,
        through="PersonPersonRelation",
        verbose_name="Related People",
    )
    roles = models.ManyToManyField(
        PersonRole,
        blank=True,
        verbose_name="Roles",
        help_text="This person's social roles.",
    )
    events = models.ManyToManyField(
        Event,
        related_name="people",
        verbose_name="Related Events",
        through="PersonEventRelation",
    )

    # sources for the information gathered here
    footnotes = GenericRelation(Footnote, blank=True, related_name="people")

    log_entries = GenericRelation(LogEntry, related_query_name="document")

    tags = TaggableManager(blank=True, related_name="tagged_person")

    # gender options
    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "U"
    GENDER_CHOICES = (
        (MALE, _("Male")),
        (FEMALE, _("Female")),
        (UNKNOWN, _("Unknown")),
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)

    date = models.CharField(
        "CE date range override",
        help_text="Manual override for automatically generated date range of this person's activity. "
        + DocumentDateMixin.standard_date_helptext,
        blank=True,  # use automatic date range from associated documents if this is blank
        null=True,
        max_length=255,
        validators=[RegexValidator(DocumentDateMixin.re_date_format)],
    )

    # minimum documents to show a page if has_page is False
    MIN_DOCUMENTS = 10

    class Meta:
        verbose_name_plural = "People"

    def generate_slug(self):
        """Override the generate_slug function for Person to prevent
        ayin, hamza, and single quotation mark from being converted
        to dashes in slug"""
        cleaned_name_str = re.sub(r"[ʿʾ']", "", str(self))
        self.slug = self.dedupe_slug(slugify(unidecode(cleaned_name_str)))

    def save(self, *args, **kwargs):
        # if slug has changed, save the old one as a past slug
        # (skip if record is not yet saved)
        if self.pk and self.has_changed("slug") and self.initial_value("slug"):
            PastPersonSlug.objects.get_or_create(
                slug=self.initial_value("slug"), person=self
            )
        super().save(*args, **kwargs)

    def __str__(self):
        """
        Display the person using their primary name, if one is designated,
        otherwise display the first name.
        """
        try:
            return str(self.names.get(primary=True))
        except Name.MultipleObjectsReturned:
            return str(self.names.filter(primary=True).first())
        except Name.DoesNotExist:
            return str(self.names.first() or super().__str__())

    @property
    def date_str(self):
        """Return a formatted string for the person's active date range, for use in public site.
        CE date override takes highest precedence, then fallback to computed date range from
        associated documents if override is unset.
        """
        return (
            standard_date_display(self.date)
            or standard_date_display(self.active_date_range)
            or ""
        )

    @property
    def deceased_date_str(self):
        """Return a formatted string for the person's mentioned as deceased date range."""
        return standard_date_display(self.deceased_date_range) or ""

    def all_roles(self):
        """Comma-separated list of a person's roles, sorted by display label or name"""
        roles = self.roles.values("display_label", "name")
        labels = sorted([(r["display_label"] or r["name"]) for r in roles])
        return ", ".join(labels)

    all_roles.short_description = "Roles"

    def solr_date_range(self):
        """Return the person's date range as a Solr date range."""
        if self.date:
            solr_dating_range = self.date.split("/")
        else:
            solr_dating_range = self.active_date_range.split("/")
        if solr_dating_range:
            # if a single date instead of a range, just return that date
            if (
                len(solr_dating_range) == 1
                or solr_dating_range[0] == solr_dating_range[1]
            ):
                return solr_dating_range[0]
            # if there's more than one date, return as a range
            return "[%s TO %s]" % tuple(solr_dating_range)

    @property
    def content_authors(self):
        """Generate a formatted string of comma-separated names of content editors/admins who
        worked on this Person's entity data, for use in a citation"""
        # get all users from log entries, order by last name
        user_pks = self.log_entries.values_list("user", flat=True)
        users = User.objects.filter(pk__in=user_pks).order_by("last_name")
        # join first and last names for each user
        get_full_name = lambda user: " ".join(
            [n for n in [user.first_name, user.last_name] if n]
        ).strip()
        full_name_list = [get_full_name(user) or user.username for user in users]
        if len(full_name_list) > 1:
            # join last two names with "and"
            and_str = ", and " if len(full_name_list) > 2 else " and "
            and_names = and_str.join(
                reversed([full_name_list.pop(), full_name_list.pop()])
            )
            # join remaining names with comma
            return ", ".join([*full_name_list, and_names])
        elif full_name_list:
            # if only one author, just return their name
            return full_name_list[0]
        else:
            return None

    @property
    def formatted_citation(self):
        """a formatted citation for display at the bottom of Person Detail pages"""
        authors = f"{self.content_authors}, " if self.content_authors else ""
        available_at = "available online through the Princeton Geniza Project at"
        today = datetime.today().strftime("%B %-d, %Y")
        return f'{authors}"{str(self)}," {available_at} {self.permalink}, accessed {today}.'

    def get_absolute_url(self):
        """url for this person"""
        if self.documents.count() >= self.MIN_DOCUMENTS or self.has_page == True:
            return reverse("entities:person", args=[str(self.slug)])
        else:
            return None

    @property
    def related_people_count(self):
        """Get a count of related people without duplicates, taking into account
        converse relationships"""
        # used for indexing and display
        people_relations = (
            self.from_person.annotate(related_id=F("from_person"))
            .values_list("related_id", flat=True)
            .union(
                self.to_person.annotate(
                    related_id=F("to_person"),
                ).values_list("related_id", flat=True)
            )
        )
        return len(set(people_relations))

    def related_people(self):
        """Set of all people related to this person, with relationship type and
        any notes on the relationship, taking into account converse relations"""

        # gather all relationships with people, both entered from this person and
        # entered from the person on the other side of the relationship
        people_relations = (
            self.from_person.annotate(
                # boolean to indicate if we should use converse or regular relation type name
                gender=F("from_person__gender"),
                use_converse_typename=Value(True),
                has_page=F("from_person__has_page"),
                related_slug=F("from_person__slug"),
                related_id=F("from_person"),
            )
            .union(  # union instead of joins for efficiency
                self.to_person.annotate(
                    gender=F("to_person__gender"),
                    use_converse_typename=Value(False),
                    has_page=F("to_person__has_page"),
                    related_slug=F("to_person__slug"),
                    related_id=F("to_person"),
                )
            )
            .values_list(
                "related_id",
                "related_slug",
                "has_page",
                "use_converse_typename",
                "gender",
                "notes",
                "type_id",
            )
        )
        # TODO: See if we can use values() now instead of values_list above,
        # then use its return value as relation_list instead of the below.
        # (will need to make sure related_id and related_slug are accessed
        # correctly in the rest of the function)
        relation_list = [
            {
                "id": r[0],
                "slug": r[1],
                "has_page": r[2],
                "use_converse_typename": r[3],
                "gender": r[4],
                "notes": r[5],
                "type_id": r[6],
            }
            for r in people_relations
        ]

        # folow GenericForeignKey to find primary name for each related person
        person_contenttype = ContentType.objects.get_for_model(Person).pk
        names = Name.objects.filter(
            object_id__in=[r["id"] for r in relation_list],
            primary=True,
            content_type_id=person_contenttype,
        ).values("name", "object_id")
        # dict keyed on related person id
        names_dict = {n["object_id"]: n["name"] for n in names}

        # grab name and converse_name for each relation type since we may need either
        # (name if the relation was entered from self, converse if entered from related person)
        types = PersonPersonRelationType.objects.filter(
            pk__in=[r["type_id"] for r in relation_list],
        ).values("pk", "name", "converse_name", "category")
        # dict keyed on related person id
        types_dict = {t["pk"]: t for t in types}

        # store each related person's documents to see if we can display their url
        related_person_docs = PersonDocumentRelation.objects.filter(
            person__id__in=[r["id"] for r in relation_list]
        ).values("document__id", "person__id")

        # efficiently get shared document counts between people by filtering doc relations
        self_docs = PersonDocumentRelation.objects.filter(
            person__id=self.pk
        ).values_list("document__id", flat=True)
        shared_docs = list(
            related_person_docs.filter(document__id__in=list(self_docs)).values(
                "document__id", "person__id"
            )
        )
        # dict keyed on related person id
        docs_dict = {
            r["person__id"]: {
                # number of shared person-doc relations matching this person's id
                "shared": len(
                    list(
                        filter(
                            lambda shared: shared["person__id"] == r["person__id"],
                            shared_docs,
                        )
                    )
                ),
                # number of total person-doc relations matching this person's id
                "total": len(
                    list(
                        filter(
                            lambda total: total["person__id"] == r["person__id"],
                            related_person_docs,
                        )
                    )
                ),
            }
            # only need to calculate these for people who have related documents
            for r in related_person_docs
        }

        # update with new data & dedupe
        prev_relation = None
        # sort by id (dedupe by matching against previous id), then type id for type dedupe
        for relation in sorted(relation_list, key=itemgetter("id", "type_id")):
            relation.update(
                {
                    # get name from cached queryset dict
                    "name": names_dict[relation["id"]],
                    # use type.converse_name if this relation is reverse (and if the type has one)
                    "type": types_dict[relation["type_id"]][
                        "converse_name" if relation["use_converse_typename"] else "name"
                    ]
                    # fallback to type.name if converse_name doesn't exist
                    or types_dict[relation["type_id"]]["name"],
                    "category": types_dict[relation["type_id"]]["category"],
                    # get count of shared documents from cached queryset dict
                    "shared_documents": (
                        docs_dict[relation["id"]]["shared"]
                        if relation["id"] in docs_dict
                        else 0
                    ),
                    # determine if this person can be linked (can if has_page is true or total docs
                    # >= Person.MIN_DOCUMENTS constant)
                    "can_link": (
                        True
                        if relation["has_page"]
                        or (
                            docs_dict[relation["id"]]["total"]
                            if relation["id"] in docs_dict
                            else 0
                        )
                        >= Person.MIN_DOCUMENTS
                        else False
                    ),
                }
            )
            # dedupe and combine type and notes
            if prev_relation and prev_relation["id"] == relation["id"]:
                # dedupe type by string matching since we can't match reverse relations by id
                if relation["type"].lower() not in prev_relation["type"].lower():
                    prev_relation["type"] += f", {relation['type']}".lower()
                # simply combine notes with html line break
                prev_relation["notes"] += (
                    f"<br />{relation['notes']}" if relation["notes"] else ""
                )
                relation_list.remove(relation)
            else:
                prev_relation = relation

        return relation_list

    @property
    def active_date_range(self):
        """Standardized range of dates across documents where a person is (presumed) alive"""
        relations = self.persondocumentrelation_set.exclude(
            type__name__icontains="deceased"
        )
        doc_ids = relations.values_list("document__pk", flat=True)
        docs = Document.objects.filter(pk__in=doc_ids).prefetch_related(
            Prefetch("dating_set", queryset=Dating.objects.only("standard_date"))
        )
        return self.get_date_range(docs)

    @property
    def deceased_date_range(self):
        """Standardized range of dates across associated documents where the relationship is
        'Mentioned (deceased)'"""
        relations = self.persondocumentrelation_set.filter(
            type__name__icontains="deceased"
        )
        doc_ids = relations.values_list("document__pk", flat=True)
        docs = Document.objects.filter(pk__in=doc_ids).prefetch_related(
            Prefetch("dating_set", queryset=Dating.objects.only("standard_date"))
        )
        return self.get_date_range(docs)

    def merge_with(self, merge_people, user=None):
        """Merge the specified people into this one. Combines all metadata
        into this person and creates a log entry documenting the merge.

        Closely adapted from :class:`Document` merge."""

        # if user is not specified, log entry will be associated with script
        if user is None:
            user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # language codes are needed to merge description, which is translated
        language_codes = [lang_code for lang_code, lang_name in settings.LANGUAGES]

        # handle translated description: create a dict of descriptions
        # per supported language to aggregate and merge
        description_chunks = {
            lang_code: [getattr(self, "description_%s" % lang_code) or ""]
            for lang_code in language_codes
        }

        # collect names as strings (since that's the important part for comparison)
        self_names = [str(name) for name in self.names.all()]

        for person in merge_people:
            # ensure any has_page overrides are respected
            self.has_page = self.has_page or person.has_page

            # migrate/copy roles and gender if not already present, check for conflicts otherwise
            if person.roles.exists():
                self.roles.add(*person.roles.all())
            if self.gender == Person.UNKNOWN and person.gender != Person.UNKNOWN:
                self.gender = person.gender
            elif person.gender != Person.UNKNOWN and self.gender != person.gender:
                raise ValidationError(
                    "Merged people must not have conflicting genders; resolve before merge"
                )

            # combine log entries (before name, since name used in log entries)
            self._merge_logentries(person)

            # combine names
            for name in person.names.all():
                if str(name) not in self_names:
                    # if not duplicated, make non-primary and add
                    name.primary = False
                    name.save()
                    self.names.add(name)

            # add description if set and not duplicated
            # for all supported languages
            for lang_code in language_codes:
                description_field = "description_%s" % lang_code
                person_description = getattr(person, description_field)
                current_description = getattr(self, description_field) or ""
                if person_description and person_description not in current_description:
                    description_chunks[lang_code].append(
                        "Description from merged entry:\n%s" % (person_description,)
                    )

            # combine person-person relationships
            # exclude relationships to primary person
            for to_relationship in person.to_person.exclude(to_person__pk=self.pk):
                # start with "to" relations (i.e. relationship to a related person was
                # added on this person's admin form); this person was "from_person"
                to_relationship.from_person = self
                to_relationship.save()
            for from_relationship in person.from_person.exclude(
                from_person__pk=self.pk
            ):
                # repeat for "from" relations (i.e. relationship to this person was added
                # on a related person's admin form); this person was "to_person"
                from_relationship.to_person = self
                from_relationship.save()

            # combine person-document relationhips
            for doc_relationship in person.persondocumentrelation_set.all():
                # prevent duplicates (by document and relation type)
                if not self.persondocumentrelation_set.filter(
                    document=doc_relationship.document,
                    type=doc_relationship.type,
                ).exists():
                    # reassign to self
                    doc_relationship.person = self
                    doc_relationship.save()

            # combine person-place relationhips
            for place_relationship in person.personplacerelation_set.all():
                # prevent duplicates (by place and relation type)
                if not self.personplacerelation_set.filter(
                    place=place_relationship.place,
                    type=place_relationship.type,
                ).exists():
                    # reassign to self
                    place_relationship.person = self
                    place_relationship.save()

            # combine footnotes
            for footnote in person.footnotes.all():
                if not self.footnotes.includes_footnote(footnote):
                    # if there is not a matching one on this person, can add footnote

                    # first remove any doc relations; person footnotes should not have
                    # doc_relation anyway, but just in case...
                    if footnote.doc_relation:
                        footnote.doc_relation = ""
                        footnote.save()

                    # then add to this person
                    self.footnotes.add(footnote)

        # combine aggregated content for text fields
        for lang_code in language_codes:
            description_field = "description_%s" % lang_code
            # combine, but filter out any None values from unset content
            setattr(
                self,
                description_field,
                "\n".join([d for d in description_chunks[lang_code] if d]),
            )

        # save current person with changes; delete merged people
        self.save()
        merged_people = ", ".join([str(person) for person in merge_people])
        for person in merge_people:
            person.delete()
        # create log entry documenting the merge; include rationale
        person_contenttype = ContentType.objects.get_for_model(Person)
        LogEntry.objects.log_action(
            user_id=user.id,
            content_type_id=person_contenttype.pk,
            object_id=self.pk,
            object_repr=str(self),
            change_message="merged with %s" % (merged_people,),
            action_flag=CHANGE,
        )

    def _merge_logentries(self, person):
        # reassociate log entries; logic for merge_with
        # make a list of currently associated log entries to skip duplicates
        current_logs = [
            "%s_%s" % (le.user_id, le.action_time.isoformat())
            for le in self.log_entries.all()
        ]
        for log_entry in person.log_entries.all():
            # check duplicate log entries, based on user id and time
            # (likely only applies to historic input & revision)
            if (
                "%s_%s" % (log_entry.user_id, log_entry.action_time.isoformat())
                in current_logs
            ):
                # skip if it's a duplicate
                continue

            # otherwise annotate and reassociate
            # - modify change message to person which object this event applied to
            log_entry.change_message = "%s [merged person %s (id = %d)]" % (
                log_entry.change_message,
                str(person),
                person.pk,
            )

            # - associate with the primary person
            log_entry.object_id = self.id
            log_entry.content_type_id = ContentType.objects.get_for_model(Person)
            log_entry.save()

    @classmethod
    def total_to_index(cls):
        """static method to efficiently count the number of documents to index in Solr"""
        # quick count for parasolr indexing (don't do prefetching just to get the total!)
        return cls.objects.count()

    @classmethod
    def items_to_index(cls):
        """Custom logic for finding items to be indexed when indexing in
        bulk."""
        return Person.objects.prefetch_related(
            "names",
            "roles",
            "relationships",
            "from_person",
            "to_person",
            "personplacerelation_set",
            Prefetch(
                "persondocumentrelation_set",
                queryset=PersonDocumentRelation.objects.select_related("type"),
            ),
            Prefetch(
                "documents",
                queryset=Document.objects.prefetch_related("dating_set"),
            ),
        )

    @classmethod
    def prep_index_chunk(cls, chunk):
        """Prefetch related information when indexing in chunks
        (modifies queryset chunk in place)"""
        models.prefetch_related_objects(
            chunk,
            "names",
            "roles",
            "relationships",
            "from_person",
            "to_person",
            "personplacerelation_set",
            Prefetch(
                "persondocumentrelation_set",
                queryset=PersonDocumentRelation.objects.select_related("type"),
            ),
            Prefetch(
                "documents",
                queryset=Document.objects.prefetch_related("dating_set"),
            ),
        )
        return chunk

    def index_data(self):
        """data for indexing in Solr"""
        index_data = super().index_data()
        url = self.get_absolute_url()
        index_data.update(
            {
                # basic metadata
                "slug_s": self.slug,
                "name_s": str(self),
                "other_names_ss": [n.name for n in self.names.non_primary()],
                "description_txt": self.description_en,
                "gender_s": self.get_gender_display(),
                "role_ss": [role.name_en for role in self.roles.all()],
                "url_s": url,
                "has_page_b": bool(url),
                # related object counts
                "documents_i": self.documents.distinct().count(),
                "people_i": self.related_people_count,
                "places_i": self.personplacerelation_set.count(),
                # kinds of relationships to documents
                "document_relation_ss": list(
                    self.persondocumentrelation_set.values_list(
                        "type__name_en", flat=True
                    ).distinct()
                ),
                "certain_document_relation_ss": list(
                    self.persondocumentrelation_set.exclude(uncertain=True)
                    .values_list("type__name_en", flat=True)
                    .distinct()
                ),
                "tags_ss_lower": [t.name for t in self.tags.all()],
            }
        )
        solr_date_range = self.solr_date_range()
        if solr_date_range:
            # date range, either from associated documents or manual override
            dates = [
                PartialDate(date)
                for date in (
                    self.date.split("/")
                    if self.date
                    else self.active_date_range.split("/")
                )
            ]
            index_data.update(
                {
                    "date_dr": solr_date_range,
                    "date_str_s": self.date_str,
                    "start_dating_i": (dates[0].numeric_format()),
                    "end_dating_i": (
                        (dates[1] if len(dates) > 1 else dates[0]).numeric_format(
                            mode="max"
                        )
                    ),
                }
            )
        return index_data

    # signal handlers to update the index based on changes to other models
    index_depends_on = {
        "names": {
            "post_save": PersonSignalHandlers.related_save,
            "pre_delete": PersonSignalHandlers.related_delete,
        },
        "roles": {
            "post_save": PersonSignalHandlers.related_save,
            "pre_delete": PersonSignalHandlers.related_delete,
        },
        "relationships": {
            "post_save": PersonSignalHandlers.related_save,
            "pre_delete": PersonSignalHandlers.related_delete,
        },
        "documents": {
            "post_save": PersonSignalHandlers.related_save,
            "pre_delete": PersonSignalHandlers.related_delete,
        },
        "personplacerelation_set": {
            "post_save": PersonSignalHandlers.related_save,
            "pre_delete": PersonSignalHandlers.related_delete,
        },
        "persondocumentrelation_set": {
            "post_save": PersonSignalHandlers.related_save,
            "pre_delete": PersonSignalHandlers.related_delete,
        },
    }


# attach pre-delete for generic relation to log entries
pre_delete.connect(detach_logentries, sender=Person)


class EntitySolrQuerySet(AliasedSolrQuerySet):
    """Mixin for shared logic between Person and Place solr queryset.
    Requires class attributes: re_solr_fields, search_aliases"""

    keyword_search_qf = (
        "{!type=edismax qf=$entities_qf pf=$entities_pf v=$keyword_query}"
    )

    def keyword_search(self, search_term):
        """Allow searching using keywords with the specified query and phrase match
        fields, and set the default operator to AND"""
        if ":" in search_term:
            # if any of the field aliases occur with a colon, replace with actual solr field
            search_term = self.re_solr_fields.sub(
                lambda x: "%s:" % self.search_aliases[x.group(1)], search_term
            )
        query_params = {"keyword_query": search_term, "q.op": "AND"}
        return self.search(self.keyword_search_qf).raw_query_parameters(
            **query_params,
        )

    def get_highlighting(self):
        """dedupe highlights across variant fields (e.g. for other_names)"""
        highlights = super().get_highlighting()
        highlights = {k: v for k, v in highlights.items() if v}
        for result in highlights.keys():
            other_names = set()
            # iterate through other_names_* fields to get all matches
            for hls in [
                highlights[result][field]
                for field in highlights[result].keys()
                if field.startswith("other_names_")
            ]:
                # strip highglight tags and whitespace, then add to set
                cleaned_names = [strip_tags(hl.strip()) for hl in hls]
                other_names.update(set(cleaned_names))
            highlights[result]["other_names"] = [n for n in other_names if n]
        return highlights


class PersonSolrQuerySet(EntitySolrQuerySet):
    """':class:`~parasolr.django.AliasedSolrQuerySet` for
    :class:`~geniza.corpus.models.Person`"""

    #: always filter to person records
    filter_qs = ["item_type_s:person"]

    #: map readable field names to actual solr fields
    field_aliases = {
        "id": "id",  # needed to match results with highlighting
        "slug": "slug_s",
        "name": "name_s",
        # need access to these other_names fields for highlighting
        "other_names_nostem": "other_names_nostem",
        "other_names_bigram": "other_names_bigram",
        "description": "description_txt",
        "gender": "gender_s",
        "roles": "role_ss",
        "url": "url_s",
        "documents": "documents_i",
        "people": "people_i",
        "places": "places_i",
        "document_relations": "document_relation_ss",
        "certain_document_relations": "certain_document_relation_ss",
        "date_str": "date_str_s",
        "has_page": "has_page_b",
        "tags": "tags_ss_lower",
    }

    search_aliases = field_aliases.copy()
    search_aliases.update(
        {
            # when searching, singular makes more sense for tags
            "tag": field_aliases["tags"],
        }
    )
    re_solr_fields = re.compile(
        r"(%s):" % "|".join(key for key, val in search_aliases.items() if key != val),
        flags=re.DOTALL,
    )


class PastPersonSlug(models.Model):
    """A slug that was previously associated with a :class:`Person`;
    preserved so that former slugs will resolve to the correct person.
    Adapted from mep-django."""

    #: person record this slug belonged to
    person = models.ForeignKey(
        Person, related_name="past_slugs", on_delete=models.CASCADE
    )
    #: slug
    slug = models.SlugField(max_length=255, unique=True)


class PersonDocumentRelationTypeManager(models.Manager):
    """Custom manager for :class:`PersonDocumentRelationType` with natural key lookup"""

    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class MergeRelationTypesMixin:
    """Mixin to include shared merge logic for relation types.
    Requires inheriting relation type model to make its relationships
    queryset available generically by the method name :meth:`relation_set`"""

    def merge_with(self, merge_relation_types, user=None):
        """Merge the specified relation types into this one. Combines all
        relationships into this relation type and creates a log entry
        documenting the merge.

        Closely adapted from :class:`Person` merge."""

        # if user is not specified, log entry will be associated with script
        if user is None:
            user = User.objects.get(username=settings.SCRIPT_USERNAME)

        for rel_type in merge_relation_types:
            # combine log entries
            for log_entry in rel_type.log_entries.all():
                # annotate and reassociate
                # - modify change message to type which object this event applied to
                log_entry.change_message = "%s [merged type %s (id = %d)]" % (
                    log_entry.get_change_message(),
                    str(rel_type),
                    rel_type.pk,
                )

                # - associate with the primary relation type
                log_entry.object_id = self.id
                log_entry.content_type_id = ContentType.objects.get_for_model(
                    self.__class__
                )
                log_entry.save()

            # combine relationships
            for relationship in rel_type.relation_set():
                # set type of each relationship to primary relation type
                relationship.type = self
                # handle unique constraint violation (one relationship per type
                # between doc and person): only reassign type if it doesn't
                # create a duplicate, otherwise delete.
                # see https://docs.djangoproject.com/en/3.2/topics/db/transactions/#django.db.transaction.atomic
                try:
                    with transaction.atomic():
                        relationship.save()
                except IntegrityError:
                    relationship.delete()

        # save current relation type with changes; delete merged relation types
        self.save()
        merged_types = ", ".join([str(rel_type) for rel_type in merge_relation_types])
        for rel_type in merge_relation_types:
            rel_type.delete()
        # create log entry documenting the merge; include rationale
        rtype_contenttype = ContentType.objects.get_for_model(self.__class__)
        LogEntry.objects.log_action(
            user_id=user.id,
            content_type_id=rtype_contenttype.pk,
            object_id=self.pk,
            object_repr=str(self),
            change_message="merged with %s" % (merged_types,),
            action_flag=CHANGE,
        )


class PersonDocumentRelationType(MergeRelationTypesMixin, models.Model):
    """Controlled vocabulary of people's relationships to documents."""

    name = models.CharField(max_length=255, unique=True)
    objects = PersonDocumentRelationTypeManager()
    log_entries = GenericRelation(
        LogEntry, related_query_name="persondocumentrelationtype"
    )

    class Meta:
        verbose_name = "Person-Document relationship"
        verbose_name_plural = "Person-Document relationships"

    def __str__(self):
        return self.name

    @cached_class_property
    def objects_by_label(cls):
        return {
            # lookup on name_en since solr should always index in English
            obj.name_en: obj
            for obj in cls.objects.all()
        }

    def relation_set(self):
        # own relationships QuerySet as required by MergeRelationTypesMixin
        return self.persondocumentrelation_set.all()


# attach pre-delete for generic relation to log entries
pre_delete.connect(detach_logentries, sender=PersonDocumentRelationType)


class PersonDocumentRelation(models.Model):
    """A relationship between a person and a document."""

    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    type = models.ForeignKey(
        PersonDocumentRelationType,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Relation",
    )
    uncertain = models.BooleanField(
        default=False,
        help_text="True if this association is inferred or uncertain. Please also include reasoning in the notes.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            # only allow one relationship per type between person and document
            models.UniqueConstraint(
                fields=("type", "person", "document"),
                name="unique_person_document_relation_by_type",
            ),
        ]

    def __str__(self):
        return f"{self.type} relation: {self.person} and {self.document}"


class PersonPersonRelationTypeManager(models.Manager):
    """Custom manager for :class:`PersonPersonRelationType` with natural key lookup"""

    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class PersonPersonRelationType(MergeRelationTypesMixin, models.Model):
    """Controlled vocabulary of people's relationships to other people."""

    # name of the relationship
    name = models.CharField(max_length=255, unique=True)
    # converse_name is the relationship in the reverse direction (the semantic converse)
    # (example: name = "Child", converse_name = "Parent")
    converse_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="""The converse of the relationship, for example, 'Child' when Name is 'Parent'.
        May leave blank if the converse is identical (for example, 'Spouse' and 'Spouse').""",
    )
    # categories for interpersonal relations:
    IMMEDIATE_FAMILY = "I"
    EXTENDED_FAMILY = "E"
    BY_MARRIAGE = "M"
    BUSINESS = "B"
    AMBIGUITY = "A"
    CATEGORY_CHOICES = (
        (IMMEDIATE_FAMILY, _("Immediate family relations")),
        (EXTENDED_FAMILY, _("Extended family")),
        (BY_MARRIAGE, _("Relatives by marriage")),
        (BUSINESS, _("Business and property relationships")),
        (AMBIGUITY, _("Ambiguity")),
    )
    category = models.CharField(
        max_length=1,
        choices=CATEGORY_CHOICES,
    )
    objects = PersonPersonRelationTypeManager()
    log_entries = GenericRelation(
        LogEntry, related_query_name="personpersonrelationtype"
    )

    class Meta:
        verbose_name = "Person-Person relationship"
        verbose_name_plural = "Person-Person relationships"

    def __str__(self):
        return self.name

    def relation_set(self):
        # own relationships QuerySet as required by MergeRelationTypesMixin
        return self.personpersonrelation_set.all()


# attach pre-delete for generic relation to log entries
pre_delete.connect(detach_logentries, sender=PersonPersonRelationType)


class PersonPersonRelation(models.Model):
    """A relationship between two people."""

    from_person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="to_person"
    )
    to_person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="from_person",
        verbose_name="Person",
    )
    type = models.ForeignKey(
        PersonPersonRelationType,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Relation",
    )
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            # only allow one relationship per type between person and person
            models.UniqueConstraint(
                fields=("type", "from_person", "to_person"),
                name="unique_person_person_relation_by_type",
            ),
            # do not allow from_person and to_person to be the same person
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_prevent_self_relationship",
                check=~models.Q(from_person=models.F("to_person")),
            ),
        ]

    def __str__(self):
        relation_type = (
            f"{self.type}-{self.type.converse_name}"
            if self.type.converse_name
            else self.type
        )
        return f"{relation_type} relation: {self.to_person} and {self.from_person}"


class PersonEventRelation(models.Model):
    """A relationship between a person and an event"""

    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Person-Event relation: {self.person} and {self.event}"


class Region(models.Model):
    """A region category for situating a :class:`Place` record geographically
    when a map is not available, such as in exports"""

    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class PlaceSignalHandlers:
    """Signal handlers for indexing :class:`Place` records when
    related records are saved or deleted."""

    # lookup from model verbose name to attribute on place
    # for use in queryset filter
    model_filter = {
        "name": "names",
        "person place relation": "personplacerelation",
        "document place relation": "documentplacerelation",
    }

    @staticmethod
    def related_change(instance, raw, mode):
        """reindex all associated people when related data is changed"""
        # common logic for save and delete
        # raw = saved as presented; don't query the database
        if raw or not instance.pk:
            return
        # get related lookup for place filter
        model_name = instance._meta.verbose_name
        place_attr = PlaceSignalHandlers.model_filter.get(model_name)
        # if handler fired on an model we don't care about, warn and exit
        if not place_attr:
            logger.warning(
                "Indexing triggered on %s but no place attribute is configured"
                % model_name
            )
            return

        place_filter = {"%s__pk" % place_attr: instance.pk}
        places = Place.items_to_index().filter(**place_filter)
        if places.exists():
            logger.debug(
                "%s %s, reindexing %d related place(s)",
                model_name,
                mode,
                places.count(),
            )
            ModelIndexable.index_items(places)

    @staticmethod
    def related_save(sender, instance=None, raw=False, **_kwargs):
        """reindex associated places when a related object is saved"""
        # delegate to common method
        PlaceSignalHandlers.related_change(instance, raw, "save")

    @staticmethod
    def related_delete(sender, instance=None, raw=False, **_kwargs):
        """reindex associated places when a related object is deleted"""
        # delegate to common method
        PlaceSignalHandlers.related_change(instance, raw, "delete")


class Place(ModelIndexable, SlugMixin, PermalinkMixin):
    """A named geographical location, which may be associated with documents or people."""

    names = GenericRelation(Name, related_query_name="place")
    latitude = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="""Latitude as a numeric value between -90 and 90, with up to 4 decimal places
        of precision. <br /><a href='https://www.fcc.gov/media/radio/dms-decimal'>This tool</a> can be
        used to convert from degrees, minutes, seconds (DMS) to decimal.""",
    )
    longitude = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="""Longitude as a numeric value between -180 and 180, with up to 4 decimal places
        of precision. <br /><a href='https://www.fcc.gov/media/radio/dms-decimal'>This tool</a> can be
        used to convert from degrees, minutes, seconds (DMS) to decimal.""",
    )
    notes = models.TextField(blank=True)
    events = models.ManyToManyField(
        Event,
        related_name="places",
        verbose_name="Related Events",
        through="PlaceEventRelation",
    )
    # sources for the information gathered here
    footnotes = GenericRelation(Footnote, blank=True, related_name="places")
    is_region = models.BooleanField(
        "Region",
        default=False,
        help_text="Please restrict entries to regions explicitly mentioned in documents.",
    )
    containing_region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The geographic region containing this place. For internal use and CSV exports only.",
    )

    def __str__(self):
        """
        Display the place using its display name, if one is designated,
        otherwise display the first name.
        """
        try:
            return str(self.names.get(primary=True))
        except Name.MultipleObjectsReturned:
            return str(self.names.filter(primary=True).first())
        except Name.DoesNotExist:
            return str(self.names.first() or super().__str__())

    def save(self, *args, **kwargs):
        # if slug has changed, save the old one as a past slug
        # (skip if record is not yet saved)
        if self.pk and self.has_changed("slug") and self.initial_value("slug"):
            PastPlaceSlug.objects.get_or_create(
                slug=self.initial_value("slug"), place=self
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """url for this place"""
        return reverse("entities:place", args=[self.slug])

    @staticmethod
    def deg_to_dms(deg, type="lat"):
        """Decimal degrees to DMS (degrees, minutes, seconds) for string display.
        Adapted from https://stackoverflow.com/a/52371976/394067"""
        decimals, number = modf(deg)
        d = int(number)
        m = int(decimals * 60)
        s = int((float(deg) - d - m / 60) * 3600.00)
        compass = {"lat": ("N", "S"), "lon": ("E", "W")}
        compass_str = compass[type][0 if d >= 0 else 1]
        return "{}° {}′ {}″ {}".format(abs(d), abs(m), abs(s), compass_str)

    @property
    def coordinates(self):
        """String formatted latitude and longitude coordinates"""
        latlon = []
        if self.latitude:
            latlon.append(self.deg_to_dms(self.latitude))
        if self.longitude:
            latlon.append(self.deg_to_dms(self.longitude, "lon"))
        return ", ".join(latlon)

    @classmethod
    def total_to_index(cls):
        """static method to efficiently count the number of people to index in Solr"""
        # quick count for parasolr indexing (don't do prefetching just to get the total!)
        return cls.objects.count()

    @classmethod
    def items_to_index(cls):
        """Custom logic for finding items to be indexed when indexing in
        bulk."""
        return Place.objects.prefetch_related(
            "names", "documentplacerelation_set", "personplacerelation_set"
        )

    def related_places(self):
        """Set of all places related to this place, with relationship type,
        taking into account converse relations"""

        # adapted from Person.related_people

        # gather all relationships with places, both entered from this place and
        # entered from the place on the other side of the relationship
        place_relations = (
            self.place_a.annotate(
                # boolean to indicate if we should use converse or regular relation type name
                use_converse_typename=Value(True),
                related_slug=F("place_a__slug"),
                related_id=F("place_a"),
            )
            .union(  # union instead of joins for efficiency
                self.place_b.annotate(
                    use_converse_typename=Value(False),
                    related_slug=F("place_b__slug"),
                    related_id=F("place_b"),
                )
            )
            .values_list(
                "related_id",
                "related_slug",
                "use_converse_typename",
                "notes",
                "type_id",
            )
        )
        # TODO: See if we can use values() now instead of values_list above,
        # then use its return value as relation_list instead of the below.
        # (will need to make sure related_id and related_slug are accessed
        # correctly in the rest of the function)
        relation_list = [
            {
                "id": r[0],
                "slug": r[1],
                "use_converse_typename": r[2],
                "notes": r[3],
                "type_id": r[4],
            }
            for r in place_relations
        ]

        # folow GenericForeignKey to find primary name for each related place
        place_contenttype = ContentType.objects.get_for_model(Place).pk
        names = Name.objects.filter(
            object_id__in=[r["id"] for r in relation_list],
            primary=True,
            content_type_id=place_contenttype,
        ).values("name", "object_id")
        # dict keyed on related place id
        names_dict = {n["object_id"]: n["name"] for n in names}

        # grab name and converse_name for each relation type since we may need either
        # (name if the relation was entered from self, converse if entered from related place)
        types = PlacePlaceRelationType.objects.filter(
            pk__in=[r["type_id"] for r in relation_list],
        ).values("pk", "name", "converse_name")
        # dict keyed on related place id
        types_dict = {t["pk"]: t for t in types}

        # update with new data & dedupe
        prev_relation = None
        # sort by id (dedupe by matching against previous id), then type id for type dedupe
        for relation in sorted(relation_list, key=itemgetter("id", "type_id")):
            relation.update(
                {
                    # get name from cached queryset dict
                    "name": names_dict[relation["id"]],
                    # use type.converse_name if this relation is reverse (and if the type has one)
                    "type": types_dict[relation["type_id"]][
                        "converse_name" if relation["use_converse_typename"] else "name"
                    ]
                    # fallback to type.name if converse_name doesn't exist
                    or types_dict[relation["type_id"]]["name"],
                }
            )
            # dedupe and combine type and notes
            if prev_relation and prev_relation["id"] == relation["id"]:
                # dedupe type by string matching since we can't match reverse relations by id
                if relation["type"].lower() not in prev_relation["type"].lower():
                    prev_relation["type"] += f", {relation['type']}".lower()
                # simply combine notes with html line break
                prev_relation["notes"] += (
                    f"<br />{relation['notes']}" if relation["notes"] else ""
                )
                relation_list.remove(relation)
            else:
                prev_relation = relation

        return relation_list

    def index_data(self):
        """data for indexing in Solr"""
        index_data = super().index_data()
        index_data.update(
            {
                # basic metadata
                "slug_s": self.slug,
                "name_s": str(self),
                "other_names_ss": sorted([n.name for n in self.names.non_primary()]),
                "url_s": self.get_absolute_url(),
                # LatLonPointSpatialField takes lat,lon string
                "location_p": (
                    f"{self.latitude},{self.longitude}"
                    if self.latitude and self.longitude
                    else None
                ),
                # related object counts
                "documents_i": self.documentplacerelation_set.count(),
                "people_i": self.personplacerelation_set.count(),
                "is_region_b": self.is_region,
            }
        )
        return index_data

    # signal handlers to update the index based on changes to other models
    index_depends_on = {
        "names": {
            "post_save": PlaceSignalHandlers.related_save,
            "pre_delete": PlaceSignalHandlers.related_delete,
        },
        "documentplacerelation_set": {
            "post_save": PlaceSignalHandlers.related_save,
            "pre_delete": PlaceSignalHandlers.related_delete,
        },
        "personplacerelation_set": {
            "post_save": PlaceSignalHandlers.related_save,
            "pre_delete": PlaceSignalHandlers.related_delete,
        },
    }


class PlaceSolrQuerySet(EntitySolrQuerySet):
    """':class:`~parasolr.django.AliasedSolrQuerySet` for
    :class:`~geniza.corpus.models.Place`"""

    #: always filter to place records
    filter_qs = ["item_type_s:place"]

    #: map readable field names to actual solr fields
    field_aliases = {
        "slug": "slug_s",
        "name": "name_s",
        "other_names": "other_names_ss",
        # copies of other_names for improved search
        "other_names_nostem": "other_names_nostem",
        "other_names_bigram": "other_names_bigram",
        "url": "url_s",
        "documents": "documents_i",
        "people": "people_i",
        "location": "location_p",
        "is_region": "is_region_b",
    }
    search_aliases = field_aliases.copy()

    re_solr_fields = re.compile(
        r"(%s):" % "|".join(key for key, val in search_aliases.items() if key != val),
        flags=re.DOTALL,
    )


class PastPlaceSlug(models.Model):
    """A slug that was previously associated with a :class:`Place`;
    preserved so that former slugs will resolve to the correct place.
    Adapted from mep-django."""

    #: place record this slug belonged to
    place = models.ForeignKey(
        Place, related_name="past_slugs", on_delete=models.CASCADE
    )
    #: slug
    slug = models.SlugField(max_length=255, unique=True)


class PersonPlaceRelationTypeManager(models.Manager):
    """Custom manager for :class:`PersonPlaceRelationType` with natural key lookup"""

    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class PersonPlaceRelationType(models.Model):
    """Controlled vocabulary of people's relationships to places."""

    name = models.CharField(max_length=255, unique=True)
    objects = PersonPlaceRelationTypeManager()

    class Meta:
        verbose_name = "Person-Place relationship"
        verbose_name_plural = "Person-Place relationships"

    def __str__(self):
        return self.name


class PersonPlaceRelation(models.Model):
    """A relationship between a person and a place."""

    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    type = models.ForeignKey(
        PersonPlaceRelationType,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Relation",
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.type} relation: {self.person} and {self.place}"


class DocumentPlaceRelationTypeManager(models.Manager):
    """Custom manager for :class:`DocumentPlaceRelationType` with natural key lookup"""

    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class DocumentPlaceRelationType(models.Model):
    """Controlled vocabulary of documents' relationships to places."""

    name = models.CharField(max_length=255, unique=True)
    objects = DocumentPlaceRelationTypeManager()

    class Meta:
        verbose_name = "Document-Place relationship"
        verbose_name_plural = "Document-Place relationships"

    def __str__(self):
        return self.name


class DocumentPlaceRelation(models.Model):
    """A relationship between a document and a place."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    type = models.ForeignKey(
        DocumentPlaceRelationType,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Relation",
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.type} relation: {self.document} and {self.place}"


class PlacePlaceRelationTypeManager(models.Manager):
    """Custom manager for :class:`PlacePlaceRelationType` with natural key lookup"""

    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class PlacePlaceRelationType(models.Model):
    """Controlled vocabulary of place's relationships to other places."""

    name = models.CharField(max_length=255, unique=True)
    # converse_name is the relationship in the reverse direction (the semantic converse)
    # (example: name = "Neighborhood", converse_name = "City")
    converse_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="The converse of the relationship, for example, 'City' when Name is "
        + "'Neighborhood'. May leave blank if the converse is identical (for example, "
        + "'Possibly the same as').",
    )
    objects = PlacePlaceRelationTypeManager()

    class Meta:
        verbose_name = "Place-Place relationship"
        verbose_name_plural = "Place-Place relationships"

    def __str__(self):
        return self.name


class PlacePlaceRelation(models.Model):
    """A relationship between two places."""

    place_a = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="place_b",
        verbose_name="Place",
    )
    place_b = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="place_a",
        verbose_name="Place",
    )
    type = models.ForeignKey(
        PlacePlaceRelationType,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Relation",
    )
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            # only allow one relationship per type between place and place
            models.UniqueConstraint(
                fields=("type", "place_a", "place_b"),
                name="unique_place_place_relation_by_type",
            ),
            # do not allow place_a and place_b to be the same place
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_prevent_self_relationship",
                check=~models.Q(place_a=models.F("place_b")),
            ),
        ]

    def __str__(self):
        relation_type = (
            f"{self.type}-{self.type.converse_name}"
            if self.type.converse_name
            else self.type
        )
        return f"{relation_type} relation: {self.place_a} and {self.place_b}"


class PlaceEventRelation(models.Model):
    """A relationship between a place and an event"""

    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Place-Event relation: {self.place} and {self.event}"

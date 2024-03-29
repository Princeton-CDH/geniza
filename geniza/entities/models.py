import re

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import RegexValidator
from django.db import models
from django.forms import ValidationError
from django.utils.translation import gettext as _
from gfklookupwidget.fields import GfkLookupField

from geniza.common.models import cached_class_property
from geniza.corpus.dates import DocumentDateMixin
from geniza.corpus.models import DisplayLabelMixin, Document, LanguageScript
from geniza.footnotes.models import Footnote


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


class Event(models.Model):
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
            or Document.standard_date_display(self.standard_date)
            or Document.standard_date_display(self.documents_date_range)
        )

    @property
    def documents_date_range(self):
        """Standardized range of dates across associated documents"""
        full_range = [None, None]
        # NOTE: This looks similar to Document.dating_range() but applies across multiple docs
        for doc in self.documents.all():
            doc_range = doc.dating_range()
            if doc_range and doc_range[0]:
                start = doc_range[0]
                end = doc_range[1] if len(doc_range) > 1 else start
                # use numeric format to compare to current min, replace if smaller
                start_numeric = int(start.numeric_format(mode="min"))
                min = full_range[0]
                if min is None or start_numeric < int(min.numeric_format(mode="min")):
                    # store as PartialDate
                    full_range[0] = start
                # use numeric format to compare to current max, replace if larger
                end_numeric = int(end.numeric_format(mode="max"))
                max = full_range[1]
                if max is None or end_numeric > int(max.numeric_format(mode="max")):
                    # store as PartialDate
                    full_range[1] = end

        # prune Nones and use isoformat for standardized representation
        full_range = [d.isoformat() for d in full_range if d]
        if len(full_range) == 2 and full_range[0] == full_range[1]:
            full_range.pop(1)
        return "/".join(full_range)


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

    class Meta:
        verbose_name = "Person social role"
        verbose_name_plural = "Person social roles"


class Person(models.Model):
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
    role = models.ForeignKey(
        PersonRole,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Role",
        help_text="Social role",
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

    class Meta:
        verbose_name_plural = "People"

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

            # migrate/copy role and gender if not already present, check for conflicts otherwise
            if person.role and not self.role:
                self.role = person.role
            elif person.role and self.role and person.role.pk != self.role.pk:
                raise ValidationError(
                    "Merged people must not have conflicting social roles; resolve before merge"
                )
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


class PersonDocumentRelationTypeManager(models.Manager):
    """Custom manager for :class:`PersonDocumentRelationType` with natural key lookup"""

    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class PersonDocumentRelationType(models.Model):
    """Controlled vocabulary of people's relationships to documents."""

    name = models.CharField(max_length=255, unique=True)
    objects = PersonDocumentRelationTypeManager()

    class Meta:
        verbose_name = "Person-Document relationship"
        verbose_name_plural = "Person-Document relationships"

    def __str__(self):
        return self.name


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


class PersonPersonRelationType(models.Model):
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

    class Meta:
        verbose_name = "Person-Person relationship"
        verbose_name_plural = "Person-Person relationships"

    def __str__(self):
        return self.name


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


class Place(models.Model):
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
        return f"{self.type} relation: {self.place_a} and {self.place_b}"


class PlaceEventRelation(models.Model):
    """A relationship between a place and an event"""

    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Place-Event relation: {self.place} and {self.event}"

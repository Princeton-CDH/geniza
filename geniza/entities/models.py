from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext as _
from gfklookupwidget.fields import GfkLookupField

from geniza.common.models import cached_class_property
from geniza.corpus.models import DisplayLabelMixin, Document, LanguageScript
from geniza.footnotes.models import Footnote


class Name(models.Model):
    """A name for an entity, such as a person or a place."""

    name = models.CharField(max_length=255)
    primary = models.BooleanField(
        default=False,
        help_text="Check box if this is the primary name that should be displayed on the site.",
        verbose_name="Display name",
    )
    language = models.ForeignKey(
        LanguageScript,
        on_delete=models.SET_NULL,
        null=True,
        help_text="Please indicate the language of most components of the name as written here.",
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

    class Meta:
        constraints = [
            # only allow one primary name per named entity
            models.UniqueConstraint(
                fields=("content_type", "object_id"),
                name="one_primary_name_per_entity",
                condition=models.Q(primary=True),
            ),
        ]

    def __str__(self):
        return self.name


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


class PersonSignalHandlers:
    """Signal handlers for :class:`taggit.Person` records."""

    @staticmethod
    def person_document_relation_changed(sender, instance, action, **kwargs):
        """After saving a person-document relation (sender), ensure the Person
        (instance) has a page if its associated docs count meets the predefined
        threshold."""
        if (
            action == "post_add"
            and not instance.has_page
            and instance.documents.count() >= Person.DOCUMENT_THRESHOLD
        ):
            instance.has_page = True
            instance.save()


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
    # sources for the information gathered here
    footnotes = models.ManyToManyField(Footnote, blank=True, related_name="people")

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

    # minimum number of documents that necessitates "has page" = true
    DOCUMENT_THRESHOLD = 10

    class Meta:
        verbose_name_plural = "People"

    def __str__(self):
        """
        Display the person using their primary name, if one is designated,
        otherwise display the first name.
        """
        try:
            return str(self.names.get(primary=True))
        except Name.DoesNotExist:
            return str(self.names.first() or super().__str__())


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

    name = models.CharField(max_length=255, unique=True)
    # categories for interpersonal relations:
    IMMEDIATE_FAMILY = "I"
    EXTENDED_FAMILY = "E"
    BY_MARRIAGE = "M"
    BUSINESS = "B"
    CATEGORY_CHOICES = (
        (IMMEDIATE_FAMILY, _("Immediate family relations")),
        (EXTENDED_FAMILY, _("Extended family")),
        (BY_MARRIAGE, _("Relatives by marriage")),
        (BUSINESS, _("Business and property relationships")),
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
        return f"{self.type} relation: {self.from_person} and {self.to_person}"

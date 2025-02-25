import pytest
from slugify import slugify

from geniza.common.tests import TestMigrations


# must run before other migrations in order to prevent Group.DoesNotExist
@pytest.mark.order(
    before="geniza/annotations/tests/test_annotations_migrations.py::TestAssociateRelatedFootnotes::test_footnote_associated"
)
@pytest.mark.django_db
class TestPopulatePersonSlugs(TestMigrations):
    app = "entities"
    migrate_from = "0022_event_permissions"
    migrate_to = "0023_person_slug"
    person = None
    person_noname = None
    person_multiname = None
    person_samename = None

    def setUpBeforeMigration(self, apps):
        Person = apps.get_model("entities", "Person")
        Name = apps.get_model("entities", "Name")
        ContentType = apps.get_model("contenttypes", "ContentType")
        person_contenttype = ContentType.objects.get(
            app_label="entities", model="person"
        )

        # normal person with a name
        self.person = Person.objects.create()
        Name.objects.create(
            name="S.D. Goitein",
            content_type=person_contenttype,
            object_id=self.person.pk,
            primary=True,
        )
        # person with no name
        self.person_noname = Person.objects.create()
        # person with multiple primary names
        self.person_multiname = Person.objects.create()
        Name.objects.create(
            name="Test Name",
            content_type=person_contenttype,
            object_id=self.person_multiname.pk,
            primary=True,
        )
        Name.objects.create(
            name="Other Primary",
            content_type=person_contenttype,
            object_id=self.person_multiname.pk,
            primary=True,
        )
        # person with the same name as another person
        self.person_samename = Person.objects.create()
        Name.objects.create(
            name="S.D. Goitein",
            content_type=person_contenttype,
            object_id=self.person_samename.pk,
            primary=True,
        )

    def test_slugs_populated(self):
        Person = self.apps.get_model("entities", "Person")
        # normal slugify
        person = Person.objects.get(pk=self.person.pk)
        assert person.slug == slugify("S.D. Goitein")

        # no name should use str
        person_noname = Person.objects.get(pk=self.person_noname.pk)
        assert person_noname.slug == slugify(str(self.person_noname))

        # multiple primary names should just pick one
        person_multiname = Person.objects.get(pk=self.person_multiname.pk)
        assert person_multiname.slug in [slugify("Test Name"), slugify("Other Primary")]

        # same name should get number
        person_samename = Person.objects.get(pk=self.person_samename.pk)
        assert person_samename.slug == f"{person.slug}-2"


@pytest.mark.order(
    before="geniza/annotations/tests/test_annotations_migrations.py::TestAssociateRelatedFootnotes::test_footnote_associated"
)
@pytest.mark.django_db
class TestPopulatePlaceSlugs(TestMigrations):
    app = "entities"
    migrate_from = "0023_person_slug"
    migrate_to = "0024_place_slug"
    place = None
    place_noname = None
    place_multiname = None
    place_samename = None

    def setUpBeforeMigration(self, apps):
        Place = apps.get_model("entities", "Place")
        Name = apps.get_model("entities", "Name")
        ContentType = apps.get_model("contenttypes", "ContentType")
        place_contenttype = ContentType.objects.get(app_label="entities", model="place")

        # normal place with a name
        self.place = Place.objects.create()
        Name.objects.create(
            name="Fustat",
            content_type=place_contenttype,
            object_id=self.place.pk,
            primary=True,
        )
        # place with no name
        self.place_noname = Place.objects.create()
        # place with multiple primary names
        self.place_multiname = Place.objects.create()
        Name.objects.create(
            name="Test Name",
            content_type=place_contenttype,
            object_id=self.place_multiname.pk,
            primary=True,
        )
        Name.objects.create(
            name="Other Primary",
            content_type=place_contenttype,
            object_id=self.place_multiname.pk,
            primary=True,
        )
        # place with the same name as another place
        self.place_samename = Place.objects.create()
        Name.objects.create(
            name="Fustat",
            content_type=place_contenttype,
            object_id=self.place_samename.pk,
            primary=True,
        )

    def test_slugs_populated(self):
        Place = self.apps.get_model("entities", "Place")
        # normal slugify
        place = Place.objects.get(pk=self.place.pk)
        assert place.slug == slugify("Fustat")

        # no name should use str
        place_noname = Place.objects.get(pk=self.place_noname.pk)
        assert place_noname.slug == slugify(str(self.place_noname))

        # multiple primary names should just pick one
        place_multiname = Place.objects.get(pk=self.place_multiname.pk)
        assert place_multiname.slug in [slugify("Test Name"), slugify("Other Primary")]

        # same name should get number
        place_samename = Place.objects.get(pk=self.place_samename.pk)
        assert place_samename.slug == f"{place.slug}-2"


@pytest.mark.order(
    before="geniza/annotations/tests/test_annotations_migrations.py::TestAssociateRelatedFootnotes::test_footnote_associated"
)
@pytest.mark.django_db
class TestSetPlaceRegions(TestMigrations):
    app = "entities"
    migrate_from = "0027_placeplacerelation_converse_name"
    migrate_to = "0028_place_is_region"
    place = None
    region = None

    def setUpBeforeMigration(self, apps):
        Place = apps.get_model("entities", "Place")
        Name = apps.get_model("entities", "Name")
        ContentType = apps.get_model("contenttypes", "ContentType")
        place_contenttype = ContentType.objects.get(app_label="entities", model="place")

        # place
        self.place = Place.objects.create()
        Name.objects.create(
            name="Fustat",
            content_type=place_contenttype,
            object_id=self.place.pk,
            primary=True,
        )
        # region
        self.region = Place.objects.create()
        Name.objects.create(
            name="Abyssinia (region)",
            content_type=place_contenttype,
            object_id=self.region.pk,
            primary=True,
        )

    def test_is_region(self):
        Place = self.apps.get_model("entities", "Place")
        # should be false
        place = Place.objects.get(pk=self.place.pk)
        assert not place.is_region

        # should be true
        region = Place.objects.get(pk=self.region.pk)
        assert region.is_region

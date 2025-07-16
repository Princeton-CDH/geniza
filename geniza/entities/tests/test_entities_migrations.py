import pytest
from slugify import slugify

from geniza.common.tests import TestMigrations
from geniza.corpus.models import Document


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


@pytest.mark.order(
    before="geniza/annotations/tests/test_annotations_migrations.py::TestAssociateRelatedFootnotes::test_footnote_associated"
)
@pytest.mark.django_db
class TestUpdatePersonSlugs(TestMigrations):
    app = "entities"
    migrate_from = "0029_persondocumentrelation_uncertain"
    migrate_to = "0030_update_person_slugs"
    person = None
    person2 = None
    person2_sameslug = None
    deleted_person = None

    def setUpBeforeMigration(self, apps):
        Person = apps.get_model("entities", "Person")
        Name = apps.get_model("entities", "Name")
        ContentType = apps.get_model("contenttypes", "ContentType")
        person_contenttype = ContentType.objects.get(
            app_label="entities", model="person"
        )

        # person to test the normal conversion
        self.person = Person.objects.create(slug="yeshu-a-b-isma-il-al-makhmuri")
        Name.objects.create(
            name="Yeshuʿa b. Ismāʿīl al-Makhmūrī",
            content_type=person_contenttype,
            object_id=self.person.pk,
            primary=True,
        )
        # people to test the unique constraint violation prevention
        self.person2 = Person.objects.create(slug="ya-aqov-b-shelomo")
        Name.objects.create(
            name="Yaʿaqov b. Shelomo",
            content_type=person_contenttype,
            object_id=self.person2.pk,
            primary=True,
        )
        self.person2_sameslug = Person.objects.create(slug="yaaqov-b-shelomo")

        deleted_person = Person.objects.create(slug="test-test")
        self.deleted_person_pk = deleted_person.pk
        Name.objects.create(
            name="testʿtest",
            content_type=person_contenttype,
            object_id=self.deleted_person_pk,
            primary=True,
        )
        deleted_person.delete()

    def test_clean_person_slugs(self):
        Person = self.apps.get_model("entities", "Person")
        PastPersonSlug = self.apps.get_model("entities", "PastPersonSlug")

        # person should have the new slug without the dash for ʿ
        person = Person.objects.get(pk=self.person.pk)
        assert "yeshu-a" not in person.slug
        assert "yeshua" in person.slug
        # should have PastPersonSlug
        assert PastPersonSlug.objects.filter(
            slug="yeshu-a-b-isma-il-al-makhmuri", person=person
        ).exists()

        # person2 should not change slugs because of the collision
        person2 = Person.objects.get(pk=self.person2.pk)
        person2_sameslug = Person.objects.get(pk=self.person2_sameslug.pk)
        assert person2.slug != person2_sameslug.slug
        assert "ya-aqov" in person2.slug
        assert "yaaqov" in person2_sameslug.slug
        # should NOT have PastPersonSlug
        assert not PastPersonSlug.objects.filter(
            slug="ya-aqov-b-shelomo", person=person2
        ).exists()

        # should have run without error on a deleted person
        assert not Person.objects.filter(pk=self.deleted_person_pk).exists()


@pytest.mark.order(
    before="geniza/annotations/tests/test_annotations_migrations.py::TestAssociateRelatedFootnotes::test_footnote_associated"
)
@pytest.mark.django_db
class TestPopulateUncertainRelations(TestMigrations):
    app = "entities"
    migrate_from = "0030_update_person_slugs"
    migrate_to = "0031_populate_persondocumentrelation_uncertain"
    possible = None
    possibly = None
    scribe_type = None
    mentioned_type = None

    def setUpBeforeMigration(self, apps):
        Person = apps.get_model("entities", "Person")
        PersonDocumentRelation = apps.get_model("entities", "PersonDocumentRelation")
        PersonDocumentRelationType = apps.get_model(
            "entities", "PersonDocumentRelationType"
        )

        person = Person.objects.create()
        # use current model since corpus is not a dependency on this migration
        document = Document.objects.create()

        (self.scribe_type, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Scribe"
        )
        (self.mentioned_type, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Mentioned"
        )

        possible_type = PersonDocumentRelationType.objects.create(
            name="Possible scribe"
        )
        self.possible = PersonDocumentRelation.objects.create(
            person=person,
            document_id=document.pk,
            type=possible_type,
        )
        possibly_type = PersonDocumentRelationType.objects.create(
            name="Possibly mentioned"
        )
        self.possibly = PersonDocumentRelation.objects.create(
            person=person,
            document_id=document.pk,
            type=possibly_type,
        )

    def test_clean_person_slugs(self):
        PersonDocumentRelation = self.apps.get_model(
            "entities", "PersonDocumentRelation"
        )

        # possible scribe relation should become "Scribe", uncertain=True
        possible = PersonDocumentRelation.objects.get(pk=self.possible.pk)
        assert possible.type.pk == self.scribe_type.pk
        assert possible.uncertain == True

        # possibly mentioned relation should become "Mentioned", uncertain=True
        possibly = PersonDocumentRelation.objects.get(pk=self.possibly.pk)
        assert possibly.type.pk == self.mentioned_type.pk
        assert possibly.uncertain == True


@pytest.mark.order(
    before="geniza/annotations/tests/test_annotations_migrations.py::TestAssociateRelatedFootnotes::test_footnote_associated"
)
@pytest.mark.django_db
class TestMigrateRoleToRoles(TestMigrations):
    app = "entities"
    migrate_from = "0031_populate_persondocumentrelation_uncertain"
    migrate_to = "0032_person_roles"
    person = None
    other_role = None

    def setUpBeforeMigration(self, apps):
        Person = apps.get_model("entities", "Person")
        PersonRole = apps.get_model("entities", "PersonRole")
        (self.other_role, _) = PersonRole.objects.get_or_create(name="Other")
        self.person = Person.objects.create(role=self.other_role)

    def test_migrate_role_to_roles(self):
        Person = self.apps.get_model("entities", "Person")
        person = Person.objects.get(pk=self.person.pk)
        assert person.roles.count() == 1
        assert self.other_role.pk in person.roles.values_list("pk", flat=True)

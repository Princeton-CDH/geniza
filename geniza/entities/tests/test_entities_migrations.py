import pytest
from slugify import slugify

from geniza.common.tests import TestMigrations


@pytest.mark.last
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

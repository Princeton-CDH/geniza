import pytest

from geniza.corpus.models import Document
from geniza.entities.models import (
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    PersonRole,
    Place,
)


@pytest.mark.django_db
class TestName:
    def test_save_unicode_cleanup(self):
        # Should cleanup \xa0 from name
        person = Person.objects.create()
        name = Name.objects.create(
            name="Shelomo\xa0 Dov Goitein", content_object=person
        )
        assert name.name == "Shelomo Dov Goitein"


@pytest.mark.django_db
class TestPerson:
    def test_str(self):
        person = Person.objects.create()
        # Person with no name uses default django __str__ method
        assert str(person) == f"Person object ({person.pk})"
        # add two names
        secondary_name = Name.objects.create(
            name="Shelomo Dov Goitein", content_object=person
        )
        primary_name = Name.objects.create(name="S.D. Goitein", content_object=person)
        # __str__ should use the first name added
        assert str(person) == secondary_name.name
        # set one of them as primary
        primary_name.primary = True
        primary_name.save()
        # __str__ should use the primary name
        assert str(person) == primary_name.name


@pytest.mark.django_db
class TestPersonRole:
    def test_objects_by_label(self):
        """Should return dict of PersonRole objects keyed on English label"""
        # invalidate cached property (it is computed in other tests in the suite)
        if "objects_by_label" in PersonRole.__dict__:
            # __dict__["objects_by_label"] returns a classmethod
            # __func__ returns a property
            # fget returns the actual cached function
            PersonRole.__dict__["objects_by_label"].__func__.fget.cache_clear()
        # add some new roles
        role = PersonRole(name_en="Some kind of official")
        role.save()
        role_2 = PersonRole(display_label_en="Example")
        role_2.save()
        # should be able to get a role by label
        assert isinstance(
            PersonRole.objects_by_label.get("Some kind of official"), PersonRole
        )
        # should match by name_en or display_label_en, depending on what's set
        assert PersonRole.objects_by_label.get("Some kind of official").pk == role.pk
        assert PersonRole.objects_by_label.get("Example").pk == role_2.pk


@pytest.mark.django_db
class TestPersonPersonRelation:
    def test_str(self):
        goitein = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=goitein)
        rustow = Person.objects.create()
        Name.objects.create(name="Marina Rustow", content_object=rustow)
        friendship_type = PersonPersonRelationType.objects.create(
            name="Friend", category=PersonPersonRelationType.BUSINESS
        )
        friendship = PersonPersonRelation.objects.create(
            from_person=goitein,
            to_person=rustow,
            type=friendship_type,
        )
        assert str(friendship) == f"{friendship_type} relation: {rustow} and {goitein}"

        # with converse_name
        ayala = Person.objects.create()
        Name.objects.create(name="Ayala Gordon", content_object=ayala)
        (parent_child, _) = PersonPersonRelationType.objects.get_or_create(
            name="Parent",
            converse_name="Child",
            category=PersonPersonRelationType.IMMEDIATE_FAMILY,
        )
        goitein_ayala = PersonPersonRelation.objects.create(
            from_person=ayala,
            to_person=goitein,
            type=parent_child,
        )
        assert str(goitein_ayala) == f"Parent-Child relation: {goitein} and {ayala}"


@pytest.mark.django_db
class TestPersonDocumentRelation:
    def test_str(self):
        goitein = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=goitein)
        recipient = PersonDocumentRelationType.objects.create(name="Test Recipient")
        doc = Document.objects.create()
        relation = PersonDocumentRelation.objects.create(
            person=goitein,
            document=doc,
            type=recipient,
        )
        assert str(relation) == f"{recipient} relation: {goitein} and {doc}"


@pytest.mark.django_db
class TestPlace:
    def test_str(self):
        place = Place.objects.create()
        # Place with no name uses default django __str__ method
        assert str(place) == f"Place object ({place.pk})"
        # add two names
        secondary_name = Name.objects.create(name="Philly", content_object=place)
        primary_name = Name.objects.create(name="Philadelphia", content_object=place)
        # __str__ should use the first name added
        assert str(place) == secondary_name.name
        # set one of them as primary
        primary_name.primary = True
        primary_name.save()
        # __str__ should use the primary name
        assert str(place) == primary_name.name


@pytest.mark.django_db
class TestPersonPlaceRelation:
    def test_str(self):
        goitein = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=goitein)
        philadelphia = Place.objects.create()
        Name.objects.create(name="Philadelphia", content_object=philadelphia)
        (home_base, _) = PersonPlaceRelationType.objects.get_or_create(name="Home base")
        relation = PersonPlaceRelation.objects.create(
            person=goitein,
            place=philadelphia,
            type=home_base,
        )
        assert str(relation) == f"{home_base} relation: {goitein} and {philadelphia}"


@pytest.mark.django_db
class TestDocumentPlaceRelation:
    def test_str(self):
        fustat = Place.objects.create()
        Name.objects.create(name="Fustat", content_object=fustat)
        (letter_origin, _) = DocumentPlaceRelationType.objects.get_or_create(
            name="Letter origin"
        )
        doc = Document.objects.create()
        relation = DocumentPlaceRelation.objects.create(
            place=fustat,
            document=doc,
            type=letter_origin,
        )
        assert str(relation) == f"{letter_origin} relation: {doc} and {fustat}"

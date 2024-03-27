from datetime import datetime

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.forms import ValidationError
from django.utils import timezone

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
    PlacePlaceRelation,
    PlacePlaceRelationType,
)
from geniza.footnotes.models import Footnote


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

    def test_merge_with(self):
        # create two people
        person = Person.objects.create(
            description_en="a person",
            gender=Person.UNKNOWN,
        )
        role = PersonRole.objects.create(name="example")
        person_2 = Person.objects.create(
            description_en="testing description",
            gender=Person.FEMALE,
            role=role,
            has_page=True,
        )
        p2_str = str(person_2)
        person.merge_with([person_2])
        # migrated public page override/missing info
        assert person.role == role
        assert person.gender == Person.FEMALE
        assert person.has_page == True
        # combined descriptions
        assert "a person" in person.description
        assert "\nDescription from merged entry:" in person.description
        assert "testing description" in person.description
        # should delete and create merge log entry
        assert not person_2.pk
        assert LogEntry.objects.filter(
            object_id=person.pk, change_message__contains=f"merged with {p2_str}"
        ).exists()

    def test_merge_with_no_description(self):
        # create two people
        person = Person.objects.create(
            gender=Person.UNKNOWN,
        )
        role = PersonRole.objects.create(name="example")
        person_2 = Person.objects.create(
            description_en="testing description",
            gender=Person.FEMALE,
            role=role,
            has_page=True,
        )
        person.merge_with([person_2])
        # should not error; should combine descriptions
        assert "Description from merged entry:" in person.description
        assert "testing description" in person.description

    def test_merge_with_conflicts(self):
        # should raise ValidationError on conflicting gender
        person = Person.objects.create(gender=Person.MALE)
        person_2 = Person.objects.create(gender=Person.FEMALE)
        with pytest.raises(ValidationError):
            person.merge_with([person_2])
        # should raise ValidationError on conflicting role
        role = PersonRole.objects.create(name="example")
        role_2 = PersonRole.objects.create(name="other")
        person_3 = Person.objects.create(gender=Person.MALE, role=role)
        person_4 = Person.objects.create(gender=Person.MALE, role=role_2)
        with pytest.raises(ValidationError):
            person_3.merge_with([person_4])

    def test_merge_with_names(self):
        person = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=person, primary=True)
        Name.objects.create(name="Shelomo Dov Goitein", content_object=person)
        person_dupe = Person.objects.create()
        dupe_name = Name.objects.create(name="S.D. Goitein", content_object=person_dupe)
        primary_name = Name.objects.create(
            name="S.D.G.", content_object=person_dupe, primary=True
        )
        person.merge_with([person_dupe])
        # identical name should not get added
        assert not person.names.filter(pk=dupe_name.pk).exists()
        # dupe's primary name should be added since it's unique, but should not be primary anymore
        assert person.names.filter(pk=primary_name.pk, primary=False).exists()

    def test_merge_with_related_people(self):
        parent = Person.objects.create()
        parent_dupe = Person.objects.create()
        child = Person.objects.create()
        grandchild = Person.objects.create()
        # "possible same" relation between person and dupe
        ambiguity_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="possibly the same as"
        )
        PersonPersonRelation.objects.create(
            from_person=parent, to_person=parent_dupe, type=ambiguity_type
        )
        # parent relation between dupe and child
        parent_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="parent", converse_name_en="child"
        )
        PersonPersonRelation.objects.create(
            from_person=parent_dupe, to_person=child, type=parent_type
        )
        # grandchild relation between grandchild and dupe
        grandchild_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="grandchild", converse_name_en="grandparent"
        )
        PersonPersonRelation.objects.create(
            from_person=grandchild, to_person=parent_dupe, type=grandchild_type
        )
        parent.merge_with([parent_dupe])

        # ambiguity relationship should no longer be present
        assert not parent.to_person.filter(type=ambiguity_type).exists()
        assert not parent.from_person.filter(type=ambiguity_type).exists()

        # child relation should be reassigned with parent as parent
        assert PersonPersonRelation.objects.filter(
            from_person=parent, to_person=child, type=parent_type
        ).exists()

        # grandchild relation should be reassigned with parent as grandparent
        assert PersonPersonRelation.objects.filter(
            from_person=grandchild, to_person=parent, type=grandchild_type
        ).exists()

    def test_merge_with_related_places(self):
        person = Person.objects.create()
        person_dupe = Person.objects.create()
        fustat = Place.objects.create()
        origin = Place.objects.create()
        home_base, _ = PersonPlaceRelationType.objects.get_or_create(
            name_en="Home base"
        )
        family_roots, _ = PersonPlaceRelationType.objects.get_or_create(
            name_en="Family traces roots to"
        )
        # both have the same home base (same place and type)
        PersonPlaceRelation.objects.create(person=person, place=fustat, type=home_base)
        PersonPlaceRelation.objects.create(
            person=person_dupe, place=fustat, type=home_base
        )
        # dupe has family origin
        PersonPlaceRelation.objects.create(
            person=person_dupe, place=origin, type=family_roots
        )
        person.merge_with([person_dupe])
        # merged should have two relations, not three (dupe skipped)
        assert person.personplacerelation_set.count() == 2
        # merged should get family origin from dupe
        assert person.personplacerelation_set.filter(
            place=origin, type=family_roots
        ).exists()

    def test_merge_with_related_documents(self, document):
        person = Person.objects.create()
        person_dupe = Person.objects.create()
        person_dupe.documents.add(document)
        person.merge_with([person_dupe])
        # document relation should be reassigned to merged result
        assert person.documents.filter(pk=document.pk).exists()

    def test_merge_with_footnotes(self, source, twoauthor_source):
        person = Person.objects.create()
        person_dupe = Person.objects.create()
        Footnote.objects.create(
            source=source, doc_relation=Footnote.EDITION, content_object=person_dupe
        )
        Footnote.objects.create(source=twoauthor_source, content_object=person)
        Footnote.objects.create(source=twoauthor_source, content_object=person_dupe)
        person.merge_with([person_dupe])
        # should have two footnotes, not three (dupe skipped)
        assert person.footnotes.count() == 2
        # first footnote should have been migrated, but had its doc relation removed
        assert person.footnotes.filter(source=source).exists()
        assert not person.footnotes.filter(doc_relation=Footnote.EDITION).exists()

    def test_merge_with_log_entries(self):
        # heavily adapted from document merge test
        person = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=person, primary=True)
        person_dupe = Person.objects.create()
        Name.objects.create(
            name="Shelomo Dov Goitein", content_object=person_dupe, primary=True
        )

        # create some log entries
        person_contenttype = ContentType.objects.get_for_model(Person)
        # creation
        creation_date = timezone.make_aware(datetime(2023, 10, 12))
        creator = User.objects.get_or_create(username="editor")[0]
        LogEntry.objects.bulk_create(
            [
                LogEntry(
                    user_id=creator.id,
                    content_type_id=person_contenttype.pk,
                    object_id=person.id,
                    object_repr=str(person),
                    change_message="first input",
                    action_flag=ADDITION,
                    action_time=creation_date,
                ),
                LogEntry(
                    user_id=creator.id,
                    content_type_id=person_contenttype.pk,
                    object_id=person_dupe.id,
                    object_repr=str(person_dupe),
                    change_message="first input",
                    action_flag=ADDITION,
                    action_time=creation_date,
                ),
                LogEntry(
                    user_id=creator.id,
                    content_type_id=person_contenttype.pk,
                    object_id=person_dupe.id,
                    object_repr=str(person_dupe),
                    change_message="major revision",
                    action_flag=CHANGE,
                    action_time=timezone.now(),
                ),
            ]
        )

        assert person.log_entries.count() == 1
        assert person_dupe.log_entries.count() == 2
        dupe_pk = person_dupe.pk
        dupe_str = str(person_dupe)
        person.merge_with([person_dupe], user=creator)
        # should have 3 log entries after the merge:
        # 1 of the two duplicates, 1 unique from dupe,
        # and 1 documenting the merge
        assert person.log_entries.count() == 3
        # based on default sorting, most recent log entry will be first
        # - should document the merge event
        merge_log = person.log_entries.first()
        # log action with specified user
        assert creator.id == merge_log.user_id
        assert merge_log.action_flag == CHANGE

        # reassociated log entry should include dupe's primary name, id
        moved_log = person.log_entries.all()[1]
        assert (
            " [merged person %s (id = %s)]" % (dupe_str, dupe_pk)
            in moved_log.change_message
        )

    def test_get_absolute_url(self):
        # should get person page url in user's language by pk
        person = Person.objects.create()
        assert person.get_absolute_url() == "/en/people/%s/" % person.pk


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

    def test_str(self):
        # str should use display label, with name as a fallback
        pr = PersonRole.objects.create(name="test")
        assert str(pr) == pr.name
        pr.display_label = "Test Display"
        assert str(pr) == pr.display_label


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


@pytest.mark.django_db
class TestPlacePlaceRelation:
    def test_str(self):
        fustat = Place.objects.create()
        Name.objects.create(name="Fustat", content_object=fustat)
        other = Place.objects.create()
        Name.objects.create(name="tatsuF", content_object=other)
        (possible_dupe, _) = PlacePlaceRelationType.objects.get_or_create(
            name="Possibly the same place as"
        )
        relation = PlacePlaceRelation.objects.create(
            place_a=fustat,
            place_b=other,
            type=possible_dupe,
        )
        assert str(relation) == f"{possible_dupe} relation: {fustat} and {other}"

import pytest

from geniza.corpus.models import Document
from geniza.entities.models import (
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonPersonRelation,
    PersonPersonRelationType,
)


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
        assert str(friendship) == f"{friendship_type} relation: {goitein} and {rustow}"


@pytest.mark.django_db
class TestPersonDocumentRelation:
    def test_str(self):
        goitein = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=goitein)
        recipient = PersonDocumentRelationType.objects.create(name="Recipient")
        doc = Document.objects.create()
        relation = PersonDocumentRelation.objects.create(
            person=goitein,
            document=doc,
            type=recipient,
        )
        assert str(relation) == f"{recipient} relation: {goitein} and {doc}"

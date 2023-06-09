import pytest

from geniza.entities.models import Name, Person


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

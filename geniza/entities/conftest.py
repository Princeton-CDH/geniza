import pytest

from geniza.entities.models import Name, Person, PersonRole


def make_person():
    (official, _) = PersonRole.objects.get_or_create(name_en="State official")
    person = Person.objects.create(gender=Person.FEMALE, role=official)
    Name.objects.create(name="Berakha bt. Yijū", content_object=person, primary=True)
    person.generate_slug()
    person.save()
    return person


def make_person_diacritic():
    (official, _) = PersonRole.objects.get_or_create(name_en="State official")
    person = Person.objects.create(gender=Person.MALE, role=official)
    Name.objects.create(
        name="Ḥalfon ha-Levi b. Netanʾel", content_object=person, primary=True
    )
    person.generate_slug()
    person.save()
    return person


def make_person_multiname():
    (community, _) = PersonRole.objects.get_or_create(name_en="Jewish community member")
    person = Person.objects.create(gender=Person.FEMALE, role=community)
    Name.objects.create(name="Zed", content_object=person, primary=True)
    Name.objects.create(name="Apple", content_object=person, primary=False)
    person.generate_slug()
    person.save()
    return person


@pytest.fixture
def person(db):
    return make_person()


@pytest.fixture
def person_diacritic(db):
    return make_person_diacritic()


@pytest.fixture
def person_multiname(db):
    return make_person_multiname()

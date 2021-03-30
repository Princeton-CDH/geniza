from django.test import TestCase

from geniza.people.models import Person

class TestPerson:
    def test_str(self):
        person = Person(first_name='Maya', last_name='Angelou')
        str(person) == 'Maya Angelou'
        person = Person(first_name='Madonna')
        str(person) == 'Madonna'
        person = Person(last_name='Queen')
        str(person) == 'Queen'

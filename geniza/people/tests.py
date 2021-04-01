from django.test import TestCase

from geniza.people.models import Person

class TestPerson:
    def test_str(self):
        person = Person(sort_name='Angelou, Maya')
        str(person) == 'Angelou, Maya'

from django import template

from geniza.entities.models import Person

register = template.Library()


@register.filter
def get_person(related_slug):
    """Template filter to retrieve a :class:`~geniza.entities.models.Person`
    by slug. Example use::

        {{ person_slug|get_person }}
    """
    return Person.objects.get(slug=related_slug)


@register.filter(name="split")
def split(to_split, split_on):
    """Template filter to split a string on a delimiter, e.g. to get latitude
    and longitude from a place location. Example use::

        {{ place.location|split:","|first }}
    """
    return to_split.split(split_on)

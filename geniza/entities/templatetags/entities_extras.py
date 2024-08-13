from django import template

from geniza.entities.models import Person

register = template.Library()


@register.filter
def get_person(related_slug):
    return Person.objects.get(slug=related_slug)


@register.filter(name="split")
def split(to_split, split_on):
    return to_split.split(split_on)

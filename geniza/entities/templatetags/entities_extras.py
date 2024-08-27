from django import template

register = template.Library()


@register.filter(name="split")
def split(to_split, split_on):
    return to_split.split(split_on)

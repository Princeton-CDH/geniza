from django import template

register = template.Library()


@register.filter
def alphabetize(value):
    """Lowercases, then alphabetizes, a list of strings"""
    if isinstance(value, list) and all(isinstance(s, str) for s in value):
        return sorted([s.lower() for s in value])
    else:
        raise TypeError("Argument must be a list of strings")

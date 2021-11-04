from django import template

register = template.Library()


@register.filter
def alphabetize(value):
    """Lowercases, then alphabetizes, a list of strings"""
    if isinstance(value, list) and all(isinstance(s, str) for s in value):
        return sorted([s.lower() for s in value])
    else:
        raise TypeError("Argument must be a list of strings")


# dict_item filter ported from ppa codebase


@register.filter
def dict_item(dictionary, key):
    """'Template filter to allow accessing dictionary value by variable key.
    Example use::

        {{ mydict|dict_item:keyvar }}
    """
    return dictionary.get(key, None)

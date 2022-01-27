from urllib import parse

from django import template
from natsort import natsorted
from piffle.iiif import IIIFImageClientException

from geniza.footnotes.models import Footnote

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


@register.simple_tag(takes_context=True)
def querystring_replace(context, **kwargs):
    """Template tag to simplify retaining querystring parameters
    when paging through search results with active filters.
    Example use::
        <a href="?{% querystring_replace page=paginator.next_page_number %}">
    """
    # borrowed as-is from derrida codebase
    # inspired by https://stackoverflow.com/questions/2047622/how-to-paginate-django-with-other-get-variables

    # get a mutable copy of the current request
    querystring = context["request"].GET.copy()
    # update with any parameters passed in
    # NOTE: needs to *set* fields rather than using update,
    # because QueryDict update appends to field rather than replacing
    for key, val in kwargs.items():
        querystring[key] = val
    # return urlencoded query string
    return querystring.urlencode()


@register.filter
def natsort(sortable, key=None):
    """Template filter to sort a list naturally, with an optional key to sort on.
    Natural sort will sort strings like ["1", "2", "3", "10"] rather than ["1", "10", "2", "3"].
    Example use::
        {% for fn in document.footnotes.all|natsort:"location" %}
            {{ fn.location }}
        {% endfor %}
    """
    return natsorted(sortable, key=lambda i: getattr(i, key) if key else None)


@register.filter
def iiif_image(img, args):
    """Add options to resize or otherwise change the display of an iiif
    image; expects an instance of :class:`piffle.iiif.IIIFImageClient`.
    Provide the method and arguments as filter string, i.e.::
        {{ myimg|iiif_image:"size:width=225,height=255" }}
    """
    # copied from mep-django

    # split into method and parameters (return if not formatted properly)
    if ":" not in args:
        return ""
    mode, opts = args.split(":")
    # split parameters into args and kwargs
    args = opts.split(",")
    # if there's an =, split it and include in kwargs dict
    kwargs = dict(arg.split("=", 1) for arg in args if "=" in arg)
    # otherwise, include as an arg
    args = [arg for arg in args if "=" not in arg]
    # attempt to call the method with the arguments
    try:
        return getattr(img, mode)(*args, **kwargs)
    except (IIIFImageClientException, TypeError):
        # return an empty string if anything goes wrong
        return ""

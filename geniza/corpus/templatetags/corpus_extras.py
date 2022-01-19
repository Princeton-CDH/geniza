from urllib import parse

from django import template
from natsort import natsorted

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
def unquote(url):
    """Template filter to parse URL-encoded URLs.

    Example use::
        <a href="{{ url|unquote }}">
    """

    return parse.unquote(url)


@register.filter
def footnotes_on_source(document, source):
    """Template filter to get all footnotes related to the passed document and source.

    Example use::
        {% for fn in document|footnotes_on_source:source %}
            {{ fn.doc_relation }}
        {% endfor %}
    """

    footnotes = source.footnote_set.filter(document=document).order_by("location")
    # use natural sort so that items like T-S 8J17.15_10, T-S 8J17.15_11
    # appear after T-S 8J17.15_2, T-S 8J17.15_3, ... T-S 8J17.15_9
    return natsorted(footnotes, key=lambda f: f.location)


@register.filter
def unique_relations_on_source(document, source):
    """Template filter to create a string for all unique document relations found on footnotes
    joining the passed document and source.

    Example use::
        {{ document|unique_relations_on_source:source }}
    """

    doc_relations = []
    # Get the full translated doc_relation names from the tuple in the model
    translated_names = dict(Footnote.DOCUMENT_RELATION_TYPES)
    # Loop through footnotes matching this document and source
    for fn in footnotes_on_source(document, source):
        for doc_relation in fn.doc_relation:
            # Append each doc relation translated name to the list
            doc_relations.append(str(translated_names[doc_relation]))
    # Join by comma to match behavior of get_FOO_display()
    return ", ".join(sorted(set(doc_relations)))

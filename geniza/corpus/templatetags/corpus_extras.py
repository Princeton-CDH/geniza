import json
import re

from django import template
from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.urls import translate_url as django_translate_url
from django.utils.safestring import mark_safe
from piffle.iiif import IIIFImageClientException

from geniza.common.utils import absolutize_url
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
    try:
        return dictionary.get(key, None)
    except AttributeError:
        # fail silently if something other than a dict is passed
        return None


@register.filter
def index(item, i):
    """'Template filter to allow accessing list element by variable index.
    Example use::

        {{ mylist|index:forloop.counter0 }}
    """
    try:
        return item[i]
    except IndexError:
        return ""


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
    # placeholder images will be a dict with an image url as value for key "info"
    elif isinstance(img, dict) and "info" in img:
        return img["info"]
    # placeholder images will be strings if this function is called again after the above call,
    # e.g. when trying to rotate images after resizing, so return as-is since placeholders will not
    # be rotated or resized
    elif isinstance(img, str):
        return img
    mode, opts = args.split(":")
    # split parameters into args and kwargs
    args = opts.split(",")
    # if there's an =, split it and include in kwargs dict
    kwargs = dict(arg.split("=", 1) for arg in args if "=" in arg)
    # use ints for rotation degrees
    kwargs = {k: (int(v) if k == "degrees" and v else v) for (k, v) in kwargs.items()}
    # otherwise, include as an arg
    args = [arg for arg in args if "=" not in arg]
    # attempt to call the method with the arguments
    try:
        return getattr(img, mode)(*args, **kwargs)
    except (IIIFImageClientException, TypeError):
        # return an empty string if anything goes wrong
        return ""


@register.filter
def iiif_info_json(images):
    """Add /info.json to a list of IIIF image IDs and dump to JSON,
    for OpenSeaDragon to parse.
    """
    return json.dumps([image["image"].info() for image in images])


@register.filter
def format_attribution(attribution):
    """format attribution for local manifests (deprecated)"""
    (attribution, additional_restrictions, extra_attrs_set) = attribution
    extra_attrs = "\n".join("<p>%s</p>" % attr for attr in extra_attrs_set)
    return '<div class="attribution"><p>%s</p><p>%s</p>%s</div>' % (
        attribution,
        additional_restrictions,
        extra_attrs,
    )


@register.filter
def pgp_urlize(text):
    """Find all instances of \"PGPID #\" in the passed text, and convert
    each to a link to the referenced document."""
    # use an absolutized placeholder URL to use for each match, replacing the fake pgpid 000 with the regex
    placeholder_url = absolutize_url(reverse("corpus:document", args=["000"])).replace(
        "000", "\g<pgpid>"
    )
    placeholder_link = '<a href="%s">\g<text></a>' % placeholder_url
    # match all instances of PGPID ### with a link to the document
    return mark_safe(
        re.sub(
            r"\b(?P<text>PGPID\b \b(?P<pgpid>\d+))\b",
            placeholder_link,
            text,
        )
    )


@register.filter
def shelfmark_wrap(shelfmark):
    """Wrap individual shelfmarks in a span within a combined shelfmark,
    to avoid wrapping mid-shelfmark"""
    return mark_safe(
        " + ".join(["<span>%s</span>" % m for m in shelfmark.split(" + ")])
    )


@register.filter
def get_document_label(result_doc):
    """Helper method to construct an appropriate aria-label for a document link
    with a fallback in case of a missing shelfmark."""
    return f'{result_doc.get("type")}: {result_doc.get("shelfmark") or "[unknown shelfmark]"}'


@register.simple_tag(takes_context=True)
def translate_url(context, lang_code):
    """Translate current full path into requested language by code."""
    # thanks to https://stackoverflow.com/a/51974042
    path = context.get("request").get_full_path()
    return django_translate_url(path, lang_code)


@register.filter
def has_location_or_url(footnotes):
    """For scholarship records list: return True if any footnote in the list
    has a URL or location."""
    return any(fn.url or fn.location for fn in footnotes)


@register.filter
def all_doc_relations(footnotes):
    """For scholarship records list: list doc relations for all footnotes."""
    relations = set()
    for fn in footnotes:
        relations.update(set([n.strip() for n in str(fn.doc_relation).split(",")]))
    return sorted(relations)


@register.filter
def is_index_cards(source):
    """For scholarship records list: indicate whether or not a source record
    relates to Goitein index cards."""
    return "unpublished index cards" in source.grouper.formatted_display(
        format_index_cards=True
    )


@register.filter
def process_citation(source):
    """For scholarship records list: handle grouped citations by passing to
    Footnote.display_multiple class method."""
    return mark_safe(Footnote.display_multiple(source.list))

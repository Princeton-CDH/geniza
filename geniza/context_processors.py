from django.conf import settings
from wagtail.core.models import Site


def template_globals(request):
    """Template context processor: add global includes (e.g.
    from django settings or site search form) for use on any page."""

    site = Site.find_for_request(request)
    context_extras = {
        "SHOW_TEST_WARNING": getattr(settings, "SHOW_TEST_WARNING", False),
        "FONT_URL_PREFIX": getattr(settings, "FONT_URL_PREFIX", ""),
        "site": site,
    }
    return context_extras

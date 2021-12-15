from django.conf import settings


def template_globals(request):
    """Template context processor: add global includes (e.g.
    from django settings or site search form) for use on any page."""

    context_extras = {
        "SHOW_TEST_WARNING": getattr(settings, "SHOW_TEST_WARNING", False),
        "FONT_URL_PREFIX": getattr(settings, "FONT_URL_PREFIX", ""),
    }
    return context_extras

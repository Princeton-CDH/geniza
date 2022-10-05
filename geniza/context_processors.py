from django.conf import settings
from wagtail.core.models import Site


def template_globals(request):
    """Template context processor: add global includes (e.g.
    from django settings or site search form) for use on any page."""

    site = Site.find_for_request(request)
    admin_language_codes = [lang[0] for lang in settings.LANGUAGES]
    context_extras = {
        "FEATURE_FLAGS": getattr(settings, "FEATURE_FLAGS", []),
        "TEST_WARNING_HEADING": getattr(settings, "TEST_WARNING_HEADING", None),
        "TEST_WARNING_MESSAGE": getattr(settings, "TEST_WARNING_MESSAGE", None),
        "FONT_URL_PREFIX": getattr(settings, "FONT_URL_PREFIX", ""),
        "PUBLIC_SITE_LANGUAGES": getattr(
            settings, "PUBLIC_SITE_LANGUAGES", admin_language_codes
        ),
        "site": site,
        "GTAGS_ANALYTICS_ID": getattr(settings, "GTAGS_ANALYTICS_ID", None),
    }
    return context_extras

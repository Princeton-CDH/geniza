from django.conf import settings
from wagtail.models import Site


def template_globals(request):
    """Template context processor: add global includes (e.g.
    from django settings or site search form) for use on any page."""

    site = Site.find_for_request(request)
    admin_language_codes = [lang[0] for lang in settings.LANGUAGES]
    context_extras = {
        "FEATURE_FLAGS": getattr(settings, "FEATURE_FLAGS", []),
        "WARNING_BANNER_HEADING": getattr(settings, "WARNING_BANNER_HEADING", None),
        "WARNING_BANNER_MESSAGE": getattr(settings, "WARNING_BANNER_MESSAGE", None),
        "FONT_URL_PREFIX": getattr(settings, "FONT_URL_PREFIX", ""),
        "PUBLIC_SITE_LANGUAGES": getattr(
            settings, "PUBLIC_SITE_LANGUAGES", admin_language_codes
        ),
        "site": site,
        "GTAGS_ANALYTICS_ID": getattr(settings, "GTAGS_ANALYTICS_ID", None),
        "IS_ARCHIVE_CRAWLER": "archive.org_bot"
        in request.META.get("HTTP_USER_AGENT", "")
        if hasattr(request, "META")
        else False,
    }
    return context_extras

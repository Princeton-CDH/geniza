from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.http import HttpRequest
from django.middleware.locale import LocaleMiddleware as DjangoLocaleMiddleware
from django.utils import translation
from django.views.i18n import set_language
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token


class PublicLocaleMiddleware:
    """Middleware to redirect anonymous users attempting to access locales that are not in
    the list of public site languages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        public_site_languages = getattr(settings, "PUBLIC_SITE_LANGUAGES", None)
        if public_site_languages and not request.user.is_authenticated:
            language_from_path = translation.get_language_from_path(request.path_info)
            if language_from_path and language_from_path not in public_site_languages:
                # if the language requested is not in public_site_languages, use default language
                default_language = settings.LANGUAGE_CODE
                language_path = request.path_info.replace(
                    language_from_path, default_language
                )
                # set request method to POST and pass default language, new path to set_language
                request.method = "POST"
                request.POST = {"language": default_language, "next": language_path}
                return set_language(request)

        # otherwise, continue on with middleware chain
        response = self.get_response(request)
        return response


class LocaleMiddleware(DjangoLocaleMiddleware):
    """ "Customize django's default locale middleware to exempt some urls from redirects"""

    # adapted from https://code.djangoproject.com/ticket/17734

    #: base paths for urls to exempt from locale redirects
    redirect_exempt_paths = ["admin", "annotations", "accounts"]

    def process_response(self, request, response):
        """exempt untranslated paths from locale redirects"""

        path_parts = request.path_info.split("/")

        # special case for iiif URIs, which are structured differently but must also be exempt
        # example URI request.path_info: /documents/1234/iiif/manifest/
        is_iiif_uri = (path_parts[3] == "iiif") if len(path_parts) > 3 else False

        base_request_path = path_parts[1]
        if base_request_path in self.redirect_exempt_paths or is_iiif_uri:
            # Prevent exempt URLs from redirecting to language-prefixed URLs
            # so that we get the expected 404 instead of a 302 redirect.
            return response

        return super().process_response(request, response)

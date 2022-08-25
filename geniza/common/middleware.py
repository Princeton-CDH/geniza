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

        base_request_path = request.path_info.split("/")[1]
        if base_request_path in self.redirect_exempt_paths:
            # Prevent exempt URLs from redirecting to language-prefixed URLs
            # so that we get the expected 404 instead of a 302 redirect.
            return response

        return super().process_response(request, response)


class TokenAuthenticationMiddleware(TokenAuthentication):
    """Extend :class:`rest_framework.authentication.TokenAuthentication` to
    create a token-auth middleware that can be used with stock Django views."""

    #: use rest_framework default Token model
    model = Token
    #: only apply to token auth annotation urls
    token_auth_base_url = "/annotations/"

    def __init__(self, get_response):
        self.get_response = get_response
        # One-time middleware configuration and initialization.

    def __call__(self, request):
        # check for token-auth user before processing the view
        self.process_request(request)
        return self.get_response(request)

    def process_request(self, request):
        """If this is a url where token auth is enabled and the user is
        not authenticated, attempt token authenticate and store resulting
        user on the request."""
        if (
            request.path.startswith(self.token_auth_base_url)
            and request.user.is_anonymous
        ):
            # NOTE: could raise exceptions in some cases...
            auth = super().authenticate(request)
            # if a user was successfully authenticated, set the user on the request
            if auth and auth[0]:
                request.user = auth[0]

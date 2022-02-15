from django.conf import settings
from django.http import HttpRequest
from django.utils import translation
from django.views.i18n import set_language


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
                request_data = {}
                request_data["language"] = default_language
                request_data["next"] = language_path
                request.POST = request_data
                return set_language(request)

        # otherwise, continue on with middleware chain
        response = self.get_response(request)
        return response

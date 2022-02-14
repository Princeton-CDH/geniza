from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import is_valid_path
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class PublicLocaleMiddleware(MiddlewareMixin):
    """Middleware to redirect anonymous users attempting to access locales that are not in
    the list of public site languages."""

    response_redirect_class = HttpResponseRedirect

    def process_request(self, request: HttpRequest):
        if settings.PUBLIC_SITE_LANGUAGES and not request.user.is_authenticated:
            language_from_path = translation.get_language_from_path(request.path_info)
            if (
                language_from_path
                and language_from_path not in settings.PUBLIC_SITE_LANGUAGES
            ):
                # If the path language isn't in the public site languages list,
                # update cookies and the request object to use the default language
                request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = settings.LANGUAGE_CODE
                translation.activate(settings.LANGUAGE_CODE)
                request.LANGUAGE_CODE = translation.get_language()

    def process_response(self, request: HttpRequest, response: HttpResponse):
        if settings.PUBLIC_SITE_LANGUAGES and not request.user.is_authenticated:
            # Compare language from request against language from path
            language = request.LANGUAGE_CODE
            language_from_path = translation.get_language_from_path(request.path_info)
            urlconf = getattr(request, "urlconf", settings.ROOT_URLCONF)
            if (
                response.status_code == 404
                and language_from_path
                and language != language_from_path
            ):
                # When attempting to access disabled language, redirect to default language
                # (which has been set on the request object)
                language_path = request.path_info.replace(language_from_path, language)
                path_valid = is_valid_path(language_path, urlconf)
                if path_valid:
                    redirect = self.response_redirect_class(language_path)
                    return redirect
        return response

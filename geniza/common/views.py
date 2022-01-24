from django.shortcuts import render
from django.utils.translation import gettext as _


def error_404(request, *args, **kwargs):
    context = {
        # Translators: title for Not Found (404) error page
        "page_title": _("Not Found"),
        # Translators: description for Not Found (404) error page
        "page_description": _("Oops, you've hit a lacuna! Page not found."),
        "page_type": "error",
    }
    return render(request, "404.html", context, status=404)


def error_500(request):
    context = {
        # Translators: title for Internal Server Error (500) error page
        "page_title": _("Server Error"),
        # Translators: description for Internal Server Error (500) error page
        "page_description": _("Something went wrong putting this page together."),
        "page_type": "error",
    }
    return render(request, "500.html", context, status=500)

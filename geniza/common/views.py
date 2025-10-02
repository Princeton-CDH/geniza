from dal import autocomplete
from django.shortcuts import render
from taggit.models import Tag


class TagAutocompleteView(autocomplete.Select2QuerySetView):
    """
    DAL autocomplete view to replace taggit-selectize for picking tags on
    taggable records. from
    https://django-autocomplete-light.readthedocs.io/en/master/taggit.html
    """

    def get_queryset(self):
        """Filter tags by name"""
        if not self.request.user.is_authenticated:
            return Tag.objects.none()

        qs = Tag.objects.all()

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs

    def get_create_option(self, context, q):
        """Handle new tag creation"""
        return []


def language_switcher(request):
    """
    Re-render the language switcher with translingual URLs based on the current request path.
    Used when the current request path is updated inside of a separate Turbo frame, rather
    than a full page load.
    """
    current_path = request.GET.get("current_path")
    return render(
        request,
        "snippets/language_switcher.html",
        {
            "current_path": current_path,
        },
    )


class SolrDownError(Exception):
    """Custom exception to indicate Solr is unreachable"""

    pass


class SolrDownMixin:
    """Mixin to use the solr_error template with a 503 status code when a view encounters a solr error"""

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except SolrDownError:
            return render(request, "solr_error.html", {}, status=503)

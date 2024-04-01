from dal import autocomplete
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, Q
from django.forms import ValidationError
from django.http import Http404, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from django.views.generic import DetailView, FormView

from geniza.entities.forms import PersonMergeForm
from geniza.entities.models import PastPersonSlug, Person, Place


class PersonMerge(PermissionRequiredMixin, FormView):
    permission_required = ("entities.change_person", "entities.delete_person")
    form_class = PersonMergeForm
    template_name = "admin/entities/person/merge.html"

    def get_success_url(self):
        return reverse("admin:entities_person_change", args=[self.primary_person.pk])

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["person_ids"] = self.person_ids
        return form_kwargs

    def get_initial(self):
        # Default to first person selected
        person_ids = self.request.GET.get("ids", None)
        if person_ids:
            self.person_ids = [int(pid) for pid in person_ids.split(",")]
            # by default, prefer the first record created
            return {"primary_person": sorted(self.person_ids)[0]}
        else:
            self.person_ids = []

    def form_valid(self, form):
        """Merge the selected people into the primary person."""
        primary_person = form.cleaned_data["primary_person"]
        self.primary_person = primary_person

        secondary_ids = [
            person_id for person_id in self.person_ids if person_id != primary_person.pk
        ]
        secondary_people = Person.objects.filter(pk__in=secondary_ids)

        # Get string representations before they are merged
        primary_person_str = f"{str(primary_person)} (id = {primary_person.pk})"
        secondary_people_str = ", ".join(
            [f"{str(person)} (id = {person.pk})" for person in secondary_people]
        )

        # Merge secondary people into the selected primary person
        user = getattr(self.request, "user", None)

        try:
            primary_person.merge_with(secondary_people, user=user)
        except ValidationError as err:
            # in case the merge resulted in an error, display error to user
            messages.error(self.request, err.message)
            # redirect to this form page instead of one of the people
            return HttpResponseRedirect(
                "%s?ids=%s"
                % (reverse("admin:person-merge"), self.request.GET.get("ids", "")),
            )

        # Display info about the merge to the user
        messages.success(
            self.request,
            mark_safe(
                f"Successfully merged {secondary_people_str} with {primary_person_str}."
            ),
        )

        return super().form_valid(form)


class UnaccentedNameAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        """entities filtered by entered query, or all entities, ordered by name"""
        q = self.request.GET.get("q", None)
        qs = self.model.objects.annotate(
            # ArrayAgg to group together related values from related model instances
            name_unaccented=ArrayAgg("names__name__unaccent", distinct=True),
        ).order_by("name_unaccented")
        if q:
            qs = qs.filter(name_unaccented__icontains=q)
        return qs


class PersonAutocompleteView(PermissionRequiredMixin, UnaccentedNameAutocompleteView):
    permission_required = ("entities.change_person",)
    model = Person


class PlaceAutocompleteView(PermissionRequiredMixin, UnaccentedNameAutocompleteView):
    permission_required = ("entities.change_place",)
    model = Place


class PersonDetailMixin(DetailView):
    """Mixin for redirecting on past slugs, to be used on all Person pages (detail
    and related objects lists)"""

    def get(self, request, *args, **kwargs):
        """extend GET to check for old slug and redirect on 404"""
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            # if not found, check for a match on a past slug
            past_slug = PastPersonSlug.objects.filter(slug=self.kwargs["slug"]).first()
            # if found, redirect to the correct url for this view
            if past_slug:
                self.kwargs["slug"] = past_slug.person.slug
                return HttpResponsePermanentRedirect(
                    past_slug.person.get_absolute_url()
                )
            # otherwise, continue raising the 404
            raise


class PersonDetailView(PersonDetailMixin):
    """public display of a single :class:`~geniza.entities.models.Person`"""

    model = Person
    context_object_name = "person"
    MIN_DOCUMENTS = 10

    def page_title(self):
        """page title, for metadata; uses Person primary name"""
        return str(self.get_object())

    def page_description(self):
        """page description, for metadata; uses truncated description"""
        return Truncator(self.get_object().description).words(20)

    def get_queryset(self, *args, **kwargs):
        """Don't show person if it does not have more than MIN_DOCUMENTS document associations
        and has_page override is False"""
        queryset = (
            super()
            .get_queryset(*args, **kwargs)
            .annotate(
                doc_count=Count("documents", distinct=True),
            )
        )
        return queryset.filter(Q(doc_count__gte=self.MIN_DOCUMENTS) | Q(has_page=True))

    def get_context_data(self, **kwargs):
        """extend context data to add page metadata"""
        context_data = super().get_context_data(**kwargs)

        context_data.update(
            {
                "page_title": self.page_title(),
                "page_description": self.page_description(),
                "page_type": "person",
            }
        )
        return context_data

from ast import literal_eval

from dal import autocomplete
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, Q
from django.forms import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from django.utils.translation import gettext as _
from django.views.generic import DetailView, FormView, ListView
from django.views.generic.edit import FormMixin

from geniza.entities.forms import PersonListForm, PersonMergeForm
from geniza.entities.models import Person, Place


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


class PersonDetailView(DetailView):
    """public display of a single :class:`~geniza.entities.models.Person`"""

    model = Person
    context_object_name = "person"

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
        return queryset.filter(
            Q(doc_count__gte=Person.MIN_DOCUMENTS) | Q(has_page=True)
        )

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


class PersonListView(ListView, FormMixin):
    model = Person
    context_object_name = "people"
    template_name = "entities/person_list.html"
    # Translators: title of people list/browse page
    page_title = _("People")
    # Translators: description of people list/browse page
    page_description = _("Browse people present in Geniza documents.")
    paginate_by = 50
    form_class = PersonListForm
    applied_filter_count = 0

    # fields to facet
    facet_fields = ["gender", "role__name", "persondocumentrelation__type__name"]

    # sort options mapped to db fields
    sort_fields = {
        "name": "name_unaccented",
        "role": "role__name",
        "documents": "documents_count",
        "people": "people_count",
        "places": "places_count",
    }
    initial = {"sort": "name", "sort_dir": "asc"}

    def get_queryset(self, *args, **kwargs):
        """modify queryset to sort and filter on people in the list"""
        people = (
            Person.objects.filter(names__primary=True).annotate(
                name_unaccented=ArrayAgg("names__name__unaccent", distinct=True),
                documents_count=Count("documents", distinct=True),
                people_count=Count("relationships", distinct=True),
                places_count=Count("personplacerelation", distinct=True),
            )
            # order people by primary name unaccented
            .order_by("name_unaccented")
        )

        form = self.get_form()
        # bail out if form is invalid
        if not form.is_valid():
            return people.none()

        # filter by each supported field
        search_opts = form.cleaned_data
        self.applied_filter_count = 0
        if "gender" in search_opts and search_opts["gender"]:
            genders = literal_eval(search_opts["gender"])
            people = people.filter(gender__in=genders)
            self.applied_filter_count += len(genders)
        if "social_role" in search_opts and search_opts["social_role"]:
            roles = literal_eval(search_opts["social_role"])
            people = people.filter(role__name__in=roles)
            self.applied_filter_count += len(roles)
        if "document_relation" in search_opts and search_opts["document_relation"]:
            relations = literal_eval(search_opts["document_relation"])
            people = people.filter(persondocumentrelation__type__name__in=relations)
            self.applied_filter_count += len(relations)
        if "sort" in search_opts and search_opts["sort"]:
            order_by = self.sort_fields[search_opts["sort"]]
            # default is ascending; handle descending by appending a - in django order_by
            if "sort_dir" in search_opts and search_opts["sort_dir"] == "desc":
                order_by = f"-{order_by}"
            people = people.order_by(order_by)

        return people

    def get_form_kwargs(self):
        """get form arguments from request and configured defaults"""
        kwargs = super().get_form_kwargs()

        # use GET instead of default POST/PUT for form data
        form_data = self.request.GET.copy()

        # set all form values to default
        for key, val in self.initial.items():
            form_data.setdefault(key, val)

        kwargs["data"] = form_data

        return kwargs

    def get_facets(self):
        """Generate counts for of each unique value of all fields in
        self.facet_fields, as a dict keyed on field name. If a field value
        is present in the database but filtered out, its count will be 0."""
        facets = {}
        form = self.get_form()
        qs = self.get_queryset()
        is_filtered = form.filters_active()
        if is_filtered:
            all_objects = self.model.objects.all()
        for field in self.facet_fields:
            # get counts of each unique value for this field in the current queryset
            facets[field] = list(
                qs.values(field).annotate(count=Count("pk", distinct=True))
            )
            if is_filtered:
                # if a filter is applied, get all values from db, not just filtered queryset
                unfiltered_values = list(
                    all_objects.values_list(field, flat=True).distinct()
                )
                # reduce to only those that are not present in filtered queryset
                remaining_values = filter(
                    lambda val: not any([d[field] == val for d in facets[field]]),
                    unfiltered_values,
                )
                # add each remaining value as a facet with a count of 0
                facets[field] += [{field: val, "count": 0} for val in remaining_values]
            # sort alphabetically by value
            facets[field] = sorted(facets[field], key=lambda d: d[field] or "")
        return facets

    def get_context_data(self, **kwargs):
        """extend context data to add page metadata, facets"""
        context_data = super().get_context_data(**kwargs)

        # set facet labels and counts on form
        facets = self.get_facets()
        context_data["form"].set_choices_from_facets(facets)

        context_data.update(
            {
                "page_title": self.page_title,
                "page_description": self.page_description,
                "page_type": "people",
                "facets": facets,
                "filter_count": self.applied_filter_count,
            }
        )
        return context_data

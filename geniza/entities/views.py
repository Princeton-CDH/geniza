import re
from ast import literal_eval
from collections import defaultdict
from urllib.parse import urlparse

from dal import autocomplete
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Count, Prefetch, Q
from django.forms import ValidationError
from django.http import (
    Http404,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
    JsonResponse,
)
from django.template.loader import render_to_string
from django.urls import resolve, reverse
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.generic import DetailView, FormView, ListView, View
from django.views.generic.edit import FormMixin
from natsort import natsort_key

from geniza.corpus.dates import DocumentDateMixin, standard_date_display
from geniza.corpus.models import Dating, Document, DocumentType, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.corpus.views import SolrDateRangeMixin
from geniza.entities.forms import (
    PersonDocumentRelationTypeMergeForm,
    PersonListForm,
    PersonMergeForm,
    PersonPersonRelationTypeMergeForm,
    PlaceListForm,
)
from geniza.entities.models import (
    DocumentPlaceRelationType,
    PastPersonSlug,
    PastPlaceSlug,
    Person,
    PersonDocumentRelationType,
    PersonPersonRelationType,
    PersonSolrQuerySet,
    Place,
    PlaceSolrQuerySet,
)


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


class RelationTypeMergeViewMixin:
    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["ids"] = self.ids
        return form_kwargs

    def get_initial(self):
        # Default to first relation type selected
        ids = self.request.GET.get("ids", None)
        if ids:
            self.ids = [int(id) for id in ids.split(",")]
            # by default, prefer the first record created
            return {"primary_relation_type": sorted(self.ids)[0]}
        else:
            self.ids = []

    def form_valid(self, form):
        """Merge the selected relation types into the primary one."""
        primary_relation_type = form.cleaned_data["primary_relation_type"]
        self.primary_relation_type = primary_relation_type

        secondary_ids = [id for id in self.ids if id != primary_relation_type.pk]
        secondary_relation_types = self.relation_type_class.objects.filter(
            pk__in=secondary_ids
        )

        # Get string representations before they are merged
        primary_relation_str = (
            f"{str(primary_relation_type)} (id = {primary_relation_type.pk})"
        )
        secondary_relation_str = ", ".join(
            [f"{str(rel)} (id = {rel.pk})" for rel in secondary_relation_types]
        )

        # Merge secondary relation types into the selected primary relation type
        user = getattr(self.request, "user", None)

        try:
            primary_relation_type.merge_with(secondary_relation_types, user=user)
        except ValidationError as err:
            # in case the merge resulted in an error, display error to user
            messages.error(self.request, err.message)
            # redirect to this form page instead of one of the items
            return HttpResponseRedirect(
                "%s?ids=%s"
                % (
                    reverse(f"admin:{self.merge_path_name}"),
                    self.request.GET.get("ids", ""),
                ),
            )

        # Display info about the merge to the user
        messages.success(
            self.request,
            mark_safe(
                f"Successfully merged {secondary_relation_str} with {primary_relation_str}."
            ),
        )

        return super().form_valid(form)


class PersonDocumentRelationTypeMerge(
    RelationTypeMergeViewMixin, PermissionRequiredMixin, FormView
):
    permission_required = (
        "entities.change_persondocumentrelationtype",
        "entities.delete_persondocumentrelationtype",
    )
    form_class = PersonDocumentRelationTypeMergeForm
    template_name = "admin/entities/persondocumentrelationtype/merge.html"
    relation_type_class = PersonDocumentRelationType
    merge_path_name = "person-document-relation-type-merge"

    def get_success_url(self):
        return reverse(
            "admin:entities_persondocumentrelationtype_change",
            args=[self.primary_relation_type.pk],
        )


class PersonPersonRelationTypeMerge(
    RelationTypeMergeViewMixin, PermissionRequiredMixin, FormView
):
    permission_required = (
        "entities.change_personpersonrelationtype",
        "entities.delete_personpersonrelationtype",
    )
    form_class = PersonPersonRelationTypeMergeForm
    template_name = "admin/entities/personpersonrelationtype/merge.html"
    relation_type_class = PersonPersonRelationType
    merge_path_name = "person-person-relation-type-merge"

    def get_success_url(self):
        return reverse(
            "admin:entities_personpersonrelationtype_change",
            args=[self.primary_relation_type.pk],
        )


class UnaccentedNameAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        """entities filtered by entered query, or all entities, ordered by name"""
        q = self.request.GET.get("q", None)
        qs = self.model.objects.annotate(
            # ArrayAgg to group together related values from related model instances
            name_unaccented=ArrayAgg("names__name__unaccent", distinct=True),
        ).order_by("name_unaccented")
        if q:
            qs = qs.filter(
                Q(name_unaccented__icontains=q) | Q(names__name__icontains=q)
            ).distinct()
        return qs


class PersonAutocompleteView(PermissionRequiredMixin, UnaccentedNameAutocompleteView):
    permission_required = ("entities.change_person",)
    model = Person

    def get_queryset(self):
        """Exclude self from queryset if in person-person form."""
        qs = super().get_queryset()
        # use forwarded constant is_person_person_form to determine if we are in the
        # person-person form, and therefore should exclude self
        if hasattr(self, "forwarded") and self.forwarded.get(
            "is_person_person_form", False
        ):
            ref_url = self.request.META.get("HTTP_REFERER", None)
            if ref_url:
                # parse HTTP_REFERER url, i.e. the current page url
                resolver_match = resolve(urlparse(ref_url)[2])
                if resolver_match and "object_id" in resolver_match.kwargs:
                    # exclude self from inline Person queryset
                    qs = qs.exclude(pk=resolver_match.kwargs["object_id"])
        return qs


class PlaceAutocompleteView(PermissionRequiredMixin, UnaccentedNameAutocompleteView):
    permission_required = ("entities.change_place",)
    model = Place


class SlugDetailMixin(DetailView):
    """Mixin for redirecting on past slugs, to be used on all Person and Place pages (detail
    and related objects lists)"""

    # NOTE: past_slug_model and past_slug_relatedfield are required for each inheriting model.
    # past_slug_relatedfield must be the inheriting model's related name from past_slug_model, i.e.
    # if past_slug_model = PastPersonSlug, then past_slug_relatedfield must be "person", because
    # PastPersonSlug.person is the field that relates back to the Person model.

    def get(self, request, *args, **kwargs):
        """extend GET to check for old slug and redirect on 404"""
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            # if not found, check for a match on a past slug
            past_slug = self.past_slug_model.objects.filter(
                slug=self.kwargs["slug"]
            ).first()
            # if found, redirect to the correct url for this view
            if past_slug:
                self.kwargs["slug"] = getattr(
                    past_slug, self.past_slug_relatedfield
                ).slug
                return HttpResponsePermanentRedirect(
                    getattr(past_slug, self.past_slug_relatedfield).get_absolute_url()
                )
            # otherwise, continue raising the 404
            raise


class PersonDetailView(SlugDetailMixin):
    """public display of a single :class:`~geniza.entities.models.Person`"""

    model = Person
    context_object_name = "person"
    MIN_DOCUMENTS = 10
    past_slug_model = PastPersonSlug
    past_slug_relatedfield = "person"

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


class RelatedDocumentsMixin:
    _page_description = None

    def page_title(self):
        """The title of the entity related documents page"""
        # Translators: title of entity "related documents" page
        return _("Related documents for %(p)s") % {"p": str(self.get_object())}

    def set_page_description(self, count):
        """Set description for an entity related documents page, with count"""
        # Translators: description of related documents page, for search engines
        self._page_description = ngettext(
            "%(count)d related document",
            "%(count)d related documents",
            count,
        ) % {
            "count": count,
        }

    def get_related(self):
        """Get and process the queryset of related documents"""
        obj = self.get_object()

        # values() fields we want, including uncertain if person-doc relation
        fields = [
            "document",
            "document__shelfmark_override",
            "document__doctype",
            "document__doc_date_original",
            "document__doc_date_standard",
            "document__doc_date_calendar",
            "type",
            "uncertain" if "person" in self.relation_field else None,
        ]
        doc_relations = getattr(obj, self.relation_field).values(
            *[f for f in fields if f]
        )

        # get needed related items in batch queries
        doc_pks = doc_relations.values_list("document", flat=True)

        # get textblocks so we can get all shelfmarks per document
        textblocks = TextBlock.objects.filter(
            certain=True, document__pk__in=doc_pks
        ).values("document__pk", "fragment__shelfmark")
        shelfmarks_by_doc = defaultdict(set)
        for tb in textblocks:
            shelfmarks_by_doc[tb["document__pk"]].add(tb["fragment__shelfmark"])

        # just for thumbnail generation, use prefetching on Document instances
        thumbnail_docs = Document.objects.filter(pk__in=doc_pks).prefetch_related(
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.filter(certain=True)
                .select_related("fragment__manifest")
                .prefetch_related("fragment__manifest__canvases"),
            )
        )
        thumbnail_docs_by_pk = {doc.pk: doc for doc in thumbnail_docs}

        # get document types
        doctypes = DocumentType.objects.filter(document__pk__in=doc_pks).values(
            "document__pk", "name", "display_label"
        )
        doctypes_by_doc = {
            d["document__pk"]: (d["display_label"] or d["name"]) for d in doctypes
        }

        # get datings
        datings = Dating.objects.filter(document__pk__in=doc_pks).values(
            "document__pk", "display_date", "standard_date"
        )
        datings_by_doc = defaultdict(list)
        for d in datings:
            datings_by_doc[d["document__pk"]].append(d)

        # get relationship types
        reltype_pks = doc_relations.values_list("type", flat=True)
        reltypes = self.relation_type_class.objects.filter(pk__in=reltype_pks).values(
            "pk", "name"
        )
        reltypes_by_pk = {r["pk"]: r["name"] for r in reltypes}

        # produce the set to render; use dict keyed on pk for deduplication
        related_documents = {}
        for rel in doc_relations:
            doc_pk = rel["document"]
            if doc_pk not in related_documents:
                # get related items by doc pk
                # translators: Label for unknown document type
                doctype_name = doctypes_by_doc.get(doc_pk, _("Unknown type"))
                doc_datings = datings_by_doc.get(doc_pk, [])
                shelfmarks = shelfmarks_by_doc.get(doc_pk, set())
                shelfmark = rel["document__shelfmark_override"] or " + ".join(
                    shelfmarks
                )
                thumbnail_doc = thumbnail_docs_by_pk.get(doc_pk)
                thumbnail = thumbnail_doc.list_thumbnail() if thumbnail_doc else ""

                # get default date display without loading entire Document into memory (as it creates sub-queries)
                original_date = (
                    " ".join(
                        [
                            rel["document__doc_date_original"],
                            dict(DocumentDateMixin.CALENDAR_CHOICES).get(
                                rel["document__doc_date_calendar"]
                            ),
                        ]
                    ).strip()
                    if rel["document__doc_date_original"]
                    else None
                )
                document_date = DocumentDateMixin.get_document_date(
                    rel["document__doc_date_standard"], original_date
                )
                if document_date:
                    # value for sorting, label for display
                    document_date = {
                        "value": rel["document__doc_date_standard"],
                        "label": document_date,
                    }
                elif doc_datings:
                    # use inferred date if one exists and no doc date
                    dating = doc_datings[0]
                    document_date = {
                        "value": dating["standard_date"],
                        "label": dating["display_date"]
                        or standard_date_display(dating["standard_date"]),
                    }

                # build the initial dict for this doc
                related_documents[doc_pk] = {
                    "pk": doc_pk,
                    "url": reverse("corpus:document", args=[str(doc_pk)]),
                    "shelfmark": shelfmark,
                    "doctype": doctype_name,
                    "relations": [],
                    "uncertain": rel.get("uncertain", None),
                    "date": document_date,
                    "thumbnail": thumbnail,
                }

            # add this relationship type to the relations list, including uncertain
            relation_name = reltypes_by_pk.get(rel["type"])
            related_documents[doc_pk]["relations"].append(
                {
                    "name": relation_name,
                    "uncertain": rel.get("uncertain", None),
                }
            )
            related_documents[doc_pk]["relations"] = sorted(
                related_documents[doc_pk]["relations"], key=lambda r: r["name"]
            )

        sort, dir = self.request.GET.get("sort", "shelfmark_asc").split("_")
        desc = dir == "desc"

        # sort by passed sort, and fallback to shelfmark as tiebreaker
        if "date" in sort:
            # sort nones at the bottom, i.e., give them the lowest date if reversed,
            # give them the highest date if not
            none_date = "0" if desc else "9999"
            sort_fn = lambda doc: (
                doc["date"]["value"] if doc["date"] else none_date,
                natsort_key(doc["shelfmark"]),
            )
        elif "relation" in sort:
            # sort uncertains after relation name
            sort_fn = lambda doc: (
                ", ".join(
                    f"{r['name']}{' (uncertain)' if r['uncertain'] else ''}"
                    for r in doc["relations"]
                ),
                natsort_key(doc["shelfmark"]),
            )
        elif "shelfmark" in sort:
            sort_fn = lambda doc: natsort_key(doc["shelfmark"])
        else:
            sort_fn = lambda doc: (doc.get(sort, ""), natsort_key(doc["shelfmark"]))
        related_documents = sorted(
            related_documents.values(), key=sort_fn, reverse=desc
        )

        self.set_page_description(len(related_documents))

        return related_documents

    def get_context_data(self, **kwargs):
        """Include list of documents and sort state in context"""

        obj = self.get_object()
        # if there are no related documents, don't serve out this page
        if not getattr(obj, self.relation_field).exists():
            raise Http404

        # otherwise, add related documents queryset to context
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "related_documents": self.get_related(),
                "sort": self.request.GET.get("sort", "shelfmark_asc"),
                # use an attribute set in get_related() to avoid extra queries for count
                "page_description": self._page_description,
            }
        )
        return context


class RelatedPeopleMixin:
    def page_title(self):
        """The title of the entity related people page"""
        # Translators: title of entity "related people" page
        return _("Related people for %(p)s") % {"p": str(self.get_object())}

    def page_description(self):
        """Description of an entity related people page, with count"""
        obj = self.get_object()
        count = getattr(obj, self.relation_field).count()
        # Translators: description of related people page, for search engines
        return ngettext(
            "%(count)d related person",
            "%(count)d related people",
            count,
        ) % {
            "count": count,
        }

    def get_related(self):
        """Get and process the queryset of related people"""
        obj = self.get_object()
        related_people = getattr(obj, self.relation_field).all()

        sort = self.request.GET.get("sort", "name_asc")

        sort_dir = "-" if sort.endswith("desc") else ""

        if "name" in sort:
            # sort by slug (stand-in for name, but diacritic insensitive)
            related_people = related_people.order_by(f"{sort_dir}person__slug")

        if "relation" in sort:
            # sort by person-entity relation type name
            related_people = related_people.order_by(f"{sort_dir}type__name")

        return related_people

    def get_context_data(self, **kwargs):
        """Include list of people and sort state in context"""

        obj = self.get_object()
        # if there are no related people, don't serve out this page
        if (
            hasattr(self, "relation_field")
            and not getattr(obj, self.relation_field).exists()
        ):
            raise Http404

        # otherwise, add related people queryset to context
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "related_people": self.get_related(),
                "sort": self.request.GET.get("sort", "name_asc"),
            }
        )
        return context


class PersonDocumentsView(RelatedDocumentsMixin, PersonDetailView):
    """List of :class:`~geniza.corpus.models.Document` objects that are related to a specific
    :class:`~geniza.entities.models.Person` (e.g., by authorship)."""

    template_name = "entities/person_related_documents.html"
    viewname = "entities:person-documents"
    relation_field = "persondocumentrelation_set"
    relation_type_class = PersonDocumentRelationType


class PersonPeopleView(RelatedPeopleMixin, PersonDetailView):
    """List of :class:`~geniza.corpus.models.Document` objects that are related to a specific
    :class:`~geniza.entities.models.Person` (e.g., by authorship)."""

    template_name = "entities/person_related_people.html"
    viewname = "entities:person-people"

    def page_description(self):
        """Description of a person related people page, with count"""
        obj = self.get_object()
        count = obj.related_people_count
        # Translators: description of related people page, for search engines
        return ngettext(
            "%(count)d related person",
            "%(count)d related people",
            count,
        ) % {
            "count": count,
        }

    def get_related(self):
        """Get and process the queryset of related people"""
        obj = self.get_object()
        related_people = obj.related_people()

        sort = self.request.GET.get("sort", "name_asc")
        reverse = sort.endswith("desc")

        if "name" in sort:
            # sort by slug (stand-in for name, but diacritic insensitive)
            related_people = sorted(
                related_people, key=lambda p: p["slug"], reverse=reverse
            )

        if "relation" in sort:
            # sort by person-entity relation type name
            related_people = sorted(
                related_people, key=lambda p: p["type"], reverse=reverse
            )

        if "documents" in sort:
            # sort by count of shared documents
            related_people = sorted(
                related_people, key=lambda p: p["shared_documents"], reverse=reverse
            )

        return related_people

    def get_context_data(self, **kwargs):
        """Extend context data to include categories for each relationship type, in order
        to make use of them in visualization"""
        relation_categories = {}
        for rel_type in PersonPersonRelationType.objects.exclude(
            category=PersonPersonRelationType.AMBIGUITY
        ):
            for relname in [rel_type.name, rel_type.converse_name]:
                relation_categories[relname] = rel_type.category
        context = super().get_context_data(**kwargs)
        context.update({"relation_categories": relation_categories})
        return context


class PersonPlacesView(PersonDetailView):
    """List of :class:`~geniza.entities.models.Place` objects that are related to a specific
    :class:`~geniza.entities.models.Person`."""

    template_name = "entities/person_related_places.html"
    viewname = "entities:person-places"

    def page_title(self):
        """The title of the person related places page"""
        # Translators: title of person "related places" page
        return _("Related places for %(p)s") % {"p": str(self.get_object())}

    def page_description(self):
        """Description of a person related places page, with count"""
        person = self.get_object()
        count = person.personplacerelation_set.count()
        # Translators: description of related places page, for search engines
        return ngettext(
            "%(count)d related place",
            "%(count)d related places",
            count,
        ) % {
            "count": count,
        }

    def get_related(self):
        """Get and process the queryset of related places"""
        person = self.get_object()
        related_places = person.personplacerelation_set.all()

        sort = self.request.GET.get("sort", "name_asc")

        sort_dir = "-" if sort.endswith("desc") else ""

        if "name" in sort:
            # sort by place name (slug)
            related_places = related_places.order_by(f"{sort_dir}place__slug")

        if "relation" in sort:
            # sort by person-place relation type name
            related_places = related_places.order_by(f"{sort_dir}type__name")

        return related_places

    def get_context_data(self, **kwargs):
        """Include list of places and sort state in context"""

        person = self.get_object()
        # if there are no related places, don't serve out this page
        if not person.personplacerelation_set.exists():
            raise Http404

        # otherwise, add related places queryset to context
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "related_places": self.get_related(),
                "sort": self.request.GET.get("sort", "name_asc"),
                "maptiler_token": getattr(settings, "MAPTILER_API_TOKEN", ""),
            }
        )
        return context


class PlaceDetailView(SlugDetailMixin):
    """public display of a single :class:`~geniza.entities.models.Place`"""

    model = Place
    context_object_name = "place"
    past_slug_model = PastPlaceSlug
    past_slug_relatedfield = "place"

    def page_title(self):
        """page title, for metadata; uses Place primary name"""
        return str(self.get_object())

    def page_description(self):
        """page description, for metadata; uses truncated notes"""
        return Truncator(self.get_object().notes).words(20)

    def get_context_data(self, **kwargs):
        """extend context data to add page metadata"""
        context_data = super().get_context_data(**kwargs)

        context_data.update(
            {
                "page_title": self.page_title(),
                "page_description": self.page_description(),
                "page_type": "place",
                "maptiler_token": getattr(settings, "MAPTILER_API_TOKEN", ""),
                "related_places": sorted(
                    self.object.related_places(), key=lambda rp: rp["type"]
                ),
            }
        )
        return context_data


class PlaceDocumentsView(RelatedDocumentsMixin, PlaceDetailView):
    """List of :class:`~geniza.corpus.models.Document` objects that are related to a specific
    :class:`~geniza.entities.models.Place` (e.g., as a letter's destination)."""

    template_name = "entities/place_related_documents.html"
    viewname = "entities:place-documents"
    relation_field = "documentplacerelation_set"
    relation_type_class = DocumentPlaceRelationType


class PlacePeopleView(RelatedPeopleMixin, PlaceDetailView):
    """List of :class:`~geniza.entities.models.Person` objects that are related to a specific
    :class:`~geniza.entities.models.Place`."""

    template_name = "entities/place_related_people.html"
    viewname = "entities:place-people"
    relation_field = "personplacerelation_set"


class PersonListView(ListView, FormMixin, SolrDateRangeMixin):
    """A list view with faceted filtering and sorting using only the Django ORM/database."""

    model = Person
    context_object_name = "people"
    template_name = "entities/person_list.html"
    # Translators: title of people list/browse page
    page_title = _("People")
    # Translators: description of people list/browse page
    page_description = _("Browse people present in Geniza documents.")
    paginate_by = 51
    form_class = PersonListForm
    applied_filter_labels = []

    # sort options mapped to solr fields
    sort_fields = {
        "relevance": "score",
        "name": "slug_s",
        "documents": "documents_i",
        "people": "people_i",
        "places": "places_i",
        "date_asc": "start_dating_i",
        "date_desc": "-end_dating_i",
    }
    initial = {"sort": "name", "sort_dir": "asc"}

    # regex to fix problematic characters in names of roles, relations, etc
    qs_regex = r"([ \(\)])"

    def get_applied_filter_labels(self, form, field, filters):
        """return a list of objects with field/value pairs, and translated labels,
        one for each applied filter"""
        labels = []
        for value in filters:
            # remove escape characters
            value = value.replace("\\", "")
            # get translated label using form helper method
            label = form.get_translated_label(field, value)
            # return object with original field and value, so we can unapply programmatically
            labels.append({"field": field, "value": value, "label": label})
        return labels

    def get_queryset(self, *args, **kwargs):
        """modify queryset to sort and filter on people in the list"""
        people = PersonSolrQuerySet().facet(
            "gender",
            "roles",
            "document_relations",
            "certain_document_relations",
            "has_page",
        )

        form = self.get_form()
        # bail out if form is invalid
        if not form.is_valid():
            return people.none()

        search_opts = form.cleaned_data
        if search_opts.get("q"):
            # keyword search query, highlighting, and relevance scoring.
            # highlight non-primary names so that we know to show them in the
            # result list if they match the query; by default they are hidden
            people = (
                people.keyword_search(search_opts["q"].replace("'", ""))
                .highlight("other_names_nostem", snippets=3, method="unified")
                .highlight("other_names_bigram", snippets=3, method="unified")
                .also("score")
            )

        self.applied_filter_labels = []
        if search_opts.get("gender"):
            genders = literal_eval(search_opts["gender"])
            people = people.filter(gender__in=genders)
            self.applied_filter_labels += self.get_applied_filter_labels(
                form, "gender", genders
            )
        if search_opts.get("date_range"):
            # date range filter; returns tuple of value or None for open-ended range
            start, end = search_opts["date_range"]
            people = people.filter(date_dr="[%s TO %s]" % (start or "*", end or "*"))
            label = "%s–%s" % (start, end)
            if start and not end:
                label = _("After %s") % start
            elif end and not start:
                label = _("Before %s") % end
            self.applied_filter_labels += [
                {
                    "field": "date_range",
                    "value": search_opts["date_range"],
                    "label": label,
                }
            ]
        if search_opts.get("has_page") == True:
            people = people.filter(has_page=True)
            self.applied_filter_labels += [
                {
                    "field": "has_page",
                    "value": "on",
                    "label": _("Detail page available"),
                }
            ]
        if search_opts.get("social_role"):
            roles = literal_eval(search_opts["social_role"])
            roles_escaped = [re.sub(self.qs_regex, r"\\\1", r) for r in roles]
            people = people.filter(roles__in=roles_escaped)
            # boost multiple selected values
            if len(roles) > 1:
                roles_field = people.field_aliases.get("roles")
                # if no keyword query entered, need to use the filter values
                # as an OR query, in order to get any relevance score
                if not search_opts.get("q"):
                    roles_q = " OR ".join(roles_escaped)
                    people = people.search(f"{roles_field}:({roles_q})")
                # use edismax boost, sum(termfreq) filter query to boost score
                # when more than one of the selected terms appears
                term_freq_boosts = ",".join(
                    [f'termfreq({roles_field},"{role}")' for role in roles]
                )
                people = people.raw_query_parameters(
                    boost=f"sum({term_freq_boosts})"
                ).also("score")
            self.applied_filter_labels += self.get_applied_filter_labels(
                form, "social_role", roles
            )
        if search_opts.get("document_relation"):
            relations = literal_eval(search_opts["document_relation"])
            relations = [re.sub(self.qs_regex, r"\\\1", r) for r in relations]
            if search_opts.get("exclude_uncertain"):
                people = people.filter(certain_document_relations__in=relations)
            else:
                people = people.filter(document_relations__in=relations)
            self.applied_filter_labels += self.get_applied_filter_labels(
                form, "document_relation", relations
            )
        if search_opts.get("sort"):
            sort_field = search_opts.get("sort")
            if "date" in sort_field:
                # date asc and desc are different fields
                if "sort_dir" in search_opts and search_opts["sort_dir"] == "desc":
                    sort_field = "date_desc"
                else:
                    sort_field = "date_asc"

            order_by = self.sort_fields[sort_field]
            # default is ascending; handle descending by appending a - in order_by
            if (
                "sort_dir" in search_opts
                and search_opts["sort_dir"] == "desc"
                and "date" not in sort_field
            ):
                order_by = f"-{order_by}"
            # use name (slug_s ascending) as tiebreaker
            people = people.order_by(order_by, "slug_s")

        self.queryset = people

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
        # get min/max configuration for person date range field
        kwargs["range_minmax"] = self.get_range_stats(
            queryset_cls=PersonSolrQuerySet, field_name="date_range"
        )

        return kwargs

    def get_context_data(self, **kwargs):
        """extend context data to add page metadata, facets"""
        context_data = super().get_context_data(**kwargs)

        # set facet labels and counts on form
        facet_dict = self.queryset.get_facets()
        # populate choices for facet filter fields on the form
        context_data["form"].set_choices_from_facets(facet_dict.facet_fields)
        # get highlighting
        paged_result = context_data["page_obj"].object_list
        highlights = paged_result.get_highlighting() if paged_result.count() else {}

        context_data.update(
            {
                "page_title": self.page_title,
                "page_description": self.page_description,
                "page_type": "people",
                "applied_filters": self.applied_filter_labels,
                "highlighting": highlights,
            }
        )
        return context_data


class PlaceListView(ListView, FormMixin, SolrDateRangeMixin):
    """A list view with faceted filtering and sorting using solr."""

    model = Place
    context_object_name = "places"
    template_name = "entities/place_list.html"
    # Translators: title of places list/browse page
    page_title = _("Places")
    # Translators: description of places list/browse page
    page_description = _("Browse places present in Geniza documents.")
    form_class = PlaceListForm
    queryset = PlaceSolrQuerySet().none()

    # sort options mapped to solr fields
    sort_fields = {
        "name": "slug_s",
        "documents": "documents_i",
        "people": "people_i",
        "relevance": "score",
    }
    initial = {"sort": "name", "sort_dir": "asc"}

    def get_form_kwargs(self):
        """get form arguments from request and configured defaults"""
        kwargs = super().get_form_kwargs()

        # use GET instead of default POST/PUT for form data
        form_data = self.request.GET.copy()

        # set all form values to default
        for key, val in self.initial.items():
            form_data.setdefault(key, val)

        kwargs["data"] = form_data

        # get min/max configuration for document date range field
        # (which is the origin of place dates, filtered by the join query)
        kwargs["range_minmax"] = self.get_range_stats(
            queryset_cls=DocumentSolrQuerySet, field_name="date_range"
        )
        # for the purposes of rendering a timeline, round to the nearest century
        dr = kwargs["range_minmax"].get("date_range")
        if dr and len(dr) == 2:
            kwargs["range_minmax"]["date_range"] = (
                dr[0] - (dr[0] % 100),  # round the lower date down
                dr[1] - (dr[1] % -100),  # round the upper date up
            )

        return kwargs

    def get_context_data(self, **kwargs):
        """extend context data to add page metadata, facets"""
        context_data = super().get_context_data(**kwargs)

        # setup config to serialize as json in template and pass to PlaceListSnippetView
        search_opts = {
            "form_valid": False,
            "snippets_url": reverse("entities:place-list-snippets"),
        }

        # can replace this with get_filter_labels if additional filters are added,
        # and/or we need to display the labels themselves
        applied_filters = []

        # get form data to pass to snippet view
        form = self.get_form()
        if form.is_valid():
            search_opts.update({"form_valid": True})
            form_data = form.cleaned_data
            if form_data.get("sort"):
                sort_field = form_data.get("sort")
                order_by = self.sort_fields[sort_field]
                # default is ascending; handle descending by appending a - in order_by
                if (
                    "sort_dir" in form_data
                    and form_data["sort_dir"] == "desc"
                    and "date" not in sort_field
                ):
                    order_by = f"-{order_by}"

                search_opts.update({"order_by": order_by})
            if form_data.get("q"):
                search_opts.update({"query": form_data.get("q")})
            date_range = form_data.get("date_range")
            if date_range:
                # add to applied_filters to show filter count
                applied_filters.append(date_range)
                search_opts.update({"date_range": date_range})

        context_data.update(
            {
                "search_opts": search_opts,
                "page_title": self.page_title,
                "page_description": self.page_description,
                "applied_filters": applied_filters,
                "total": PlaceSolrQuerySet().count(),
                "page_type": "places",
                "maptiler_token": getattr(settings, "MAPTILER_API_TOKEN", ""),
            }
        )
        return context_data


class PlaceListSnippetView(View):
    """A view used in :class:`PlaceListView` to render snippets of paginated
    place results asynchronously: markers to be displayed on the map, and search
    results for the list."""

    paginate_by = 100

    def get(self, *args, **kwargs):
        """Return a JSON response with the rendered snippets, based on the
        modified queryset and pagination params in the GET request."""
        # handle sorting and filtering on solr queryset
        places = PlaceSolrQuerySet()
        query = self.request.GET.get("q")
        if query:
            # keyword search query and relevance scoring
            places = places.keyword_search(query.replace("'", "")).also("score")

        # handle date filter
        date_range = self.request.GET.get("date_range")
        if date_range:
            start_date, end_date = date_range.split(",")
            places = places.filter(
                f"{{!join from=places_ids_ss to=id}}item_type_s:document AND document_date_dr:[{start_date or '*'} TO {end_date or '*'}]"
            )

        order_by = self.request.GET.get("sort", "slug_s")
        places = places.order_by(order_by)

        count = places.count()
        # Translators: number of results
        count_str = ngettext("%(count)d result", "%(count)d results", count) % {
            "count": count
        }
        # Translators: number of places
        button_count_str = ngettext("%(count)d place", "%(count)d places", count) % {
            "count": count
        }  # different verbiage for the "toggle to list mode" mobile button

        # handle pagination
        paginator = Paginator(places, self.paginate_by)
        page_number = self.request.GET.get("page", 1)
        page = paginator.get_page(page_number)

        # render the snippets to HTML strings so we can asynchronously insert them
        # with JS
        markers_snippet = render_to_string(
            "entities/snippets/place_markers.html",
            {
                "places": [p for p in page if "location" in p],
                "has_next": page.has_next(),
            },
        )
        results_snippet = render_to_string(
            "entities/snippets/place_results.html", {"places": page}
        )

        # use JSON response since we don't need any additional template rendering,
        # and this will allow Stimulus to work with the data easily
        return JsonResponse(
            {
                "markers_snippet": markers_snippet,
                "results_snippet": results_snippet,
                "has_next": page.has_next(),
                "next_page_number": (
                    page.next_page_number() if page.has_next() else None
                ),
                "results_count": count_str,
                "places_count": button_count_str,
            }
        )

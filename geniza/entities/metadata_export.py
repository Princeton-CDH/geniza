from django.db.models.query import Prefetch
from django.utils.text import slugify

from geniza.common.metadata_export import Exporter
from geniza.corpus.dates import standard_date_display
from geniza.corpus.models import Document
from geniza.entities.models import (
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Event,
    Person,
    PersonDocumentRelation,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    Place,
    PlaceEventRelation,
)


class PublicPersonExporter(Exporter):
    """
    A subclass of :class:`geniza.common.metadata_export.Exporter` that
    exports information relating to :class:`~geniza.entities.models.Person`.
    Extends :meth:`get_queryset` and :meth:`get_export_data_dict`.
    """

    model = Person
    csv_fields = [
        "name",
        "name_variants",
        "gender",
        "social_role",
        # TODO: floruit vs mentioned as dead date columns
        "auto_date_range",
        "manual_date_range",
        "description",
        "related_people_count",
        "related_documents_count",
        "url",
    ]

    # queryset filter for content types included in this export
    content_type_filter = {
        "content_type__app_label__in": ["entities", "corpus"],
        "content_type__model__in": [
            "Dating",
            "Document",
            "Name",
            "Person",
            "PersonDocumentRelation",
            "PersonPersonRelation",
            "PersonPlaceRelation",
            "PersonRole",
            "Place",
        ],
    }

    def __init__(self, queryset=None, progress=False):
        """Adds fields to the export based on PersonPlaceRelationType names"""
        self.csv_fields[9:9] = [
            slugify(ppr_type.name).replace("-", "_")
            for ppr_type in PersonPlaceRelationType.objects.order_by("name")
        ]
        super().__init__(queryset, progress)

    def get_queryset(self):
        """
        Applies some prefetching to the base Exporter's get_queryset functionality.

        :return: Custom-given query set or query set of all people
        :rtype: QuerySet
        """
        qset = self.queryset or self.model.objects.all()
        # clear existing prefetches and then add the ones we need
        qset = (
            qset.prefetch_related(None)
            .prefetch_related(
                "names",
                "role",
                "relationships",
                "from_person",
                "to_person",
                "personplacerelation_set",
                Prefetch(
                    "persondocumentrelation_set",
                    queryset=PersonDocumentRelation.objects.select_related("type"),
                ),
                Prefetch(
                    "documents",
                    queryset=Document.objects.prefetch_related("dating_set"),
                ),
            )
            .order_by("slug")
        )
        return qset

    def get_export_data_dict(self, person):
        """
        Get back data about a person in dictionary format.

        :param person: A given Person object
        :type person: Person

        :return: Dictionary of data about the person
        :rtype: dict
        """
        outd = {
            "name": str(person),
            "name_variants": ", ".join(
                sorted([n.name for n in person.names.non_primary()])
            ),
            "gender": person.get_gender_display(),
            "social_role": str(person.role),
            "auto_date_range": standard_date_display(person.documents_date_range),
            "manual_date_range": person.date,
            "description": person.description,
            "related_people_count": person.related_people_count,
            "related_documents_count": person.documents.count(),
        }

        # add url if present
        if person.get_absolute_url():
            outd["url"] = person.permalink

        # grop related places by relation type name
        related_places = PersonPlaceRelation.objects.filter(
            person__id=person.pk
        ).values("place__id", "type__name")
        rel_types = related_places.values_list("type__name", flat=True).distinct()
        related_place_ids = {}
        for type_name in rel_types:
            related_place_ids[type_name] = (
                related_places.filter(type__name=type_name)
                .values_list("place__id", flat=True)
                .distinct()
            )

        # get names of related places (grouped by type name) and set on output dict
        for [type_name, place_ids] in related_place_ids.items():
            outd[slugify(type_name).replace("-", "_")] = ", ".join(
                sorted([str(place) for place in Place.objects.filter(id__in=place_ids)])
            )

        return outd


class AdminPersonExporter(PublicPersonExporter):
    csv_fields = PublicPersonExporter.csv_fields + ["url_admin"]

    def get_export_data_dict(self, person):
        """
        Adding certain fields to PublicPersonExporter.get_export_data_dict that are admin-only.
        """

        outd = super().get_export_data_dict(person)
        outd[
            "url_admin"
        ] = f"{self.url_scheme}{self.site_domain}/admin/entities/person/{person.id}/change/"

        return outd


class PublicPlaceExporter(Exporter):
    """
    A subclass of :class:`geniza.common.metadata_export.Exporter` that
    exports information relating to :class:`~geniza.entities.models.Place`.
    Extends :meth:`get_queryset` and :meth:`get_export_data_dict`.
    """

    model = Place
    csv_fields = [
        "name",
        "name_variants",
        "coordinates",
        "notes",
        "url",
    ]

    # queryset filter for content types included in this export
    content_type_filter = {
        "content_type__app_label__in": ["entities", "corpus"],
        "content_type__model__in": [
            "Document",
            "DocumentPlaceRelation",
            "DocumentPlaceRelationType",
            "Name",
            "Person",
            "PersonPlaceRelation",
            "PersonPlaceRelationType",
            "Place",
        ],
    }

    def get_queryset(self):
        """
        Applies some prefetching to the base Exporter's get_queryset functionality.

        :return: Custom-given query set or query set of all people
        :rtype: QuerySet
        """
        qset = self.queryset or self.model.objects.all()
        # clear existing prefetches and then add the ones we need
        qset = (
            qset.prefetch_related(None)
            .prefetch_related(
                "names",
                "events",
                Prefetch(
                    "personplacerelation_set",
                    queryset=PersonPlaceRelation.objects.select_related("type"),
                ),
                Prefetch(
                    "documentplacerelation_set",
                    queryset=DocumentPlaceRelation.objects.select_related("type"),
                ),
            )
            .order_by("slug")
        )
        return qset

    def get_export_data_dict(self, place):
        """
        Get back data about a place in dictionary format.

        :param place: A given Place object
        :type place: Place

        :return: Dictionary of data about the place
        :rtype: dict
        """
        outd = {
            "name": str(place),
            "name_variants": ", ".join(
                sorted([n.name for n in place.names.non_primary()])
            ),
            "coordinates": place.coordinates,
            "notes": place.notes,
            "url": place.permalink,
        }

        return outd


class AdminPlaceExporter(PublicPlaceExporter):
    csv_fields = PublicPlaceExporter.csv_fields + [
        "events",
        "url_admin",
    ]

    def __init__(self, queryset=None, progress=False):
        """Adds fields to the export based on relation type names"""
        rel_types = [
            ("people", PersonPlaceRelationType.objects.order_by("name")),
            ("documents", DocumentPlaceRelationType.objects.order_by("name")),
        ]
        self.csv_fields[5:5] = [
            slugify(rel_type.name).replace("-", "_") + f"_{rel_class}"
            for (rel_class, rts) in rel_types
            for rel_type in rts
        ]
        super().__init__(queryset, progress)

    def get_export_data_dict(self, place):
        """
        Adding certain fields to PublicPlaceExporter.get_export_data_dict that are admin-only.
        """
        outd = super().get_export_data_dict(place)

        # grop related people by relation type name
        related_people = PersonPlaceRelation.objects.filter(place__id=place.id).values(
            "person__id", "type__name"
        )
        rel_types = related_people.values_list("type__name", flat=True).distinct()
        related_person_ids = {}
        for type_name in rel_types:
            related_person_ids[type_name] = (
                related_people.filter(type__name=type_name)
                .values_list("person__id", flat=True)
                .distinct()
            )

        # get names of related people (grouped by type name) and set on output dict
        for [type_name, person_ids] in related_person_ids.items():
            tn = slugify(type_name).replace("-", "_")
            outd[f"{tn}_people"] = ", ".join(
                sorted(
                    [str(person) for person in Person.objects.filter(id__in=person_ids)]
                )
            )

        # grop related documents by relation type name
        related_docs = DocumentPlaceRelation.objects.filter(place__id=place.id).values(
            "document__id", "type__name"
        )
        rel_types = related_docs.values_list("type__name", flat=True).distinct()
        related_doc_ids = {}
        for type_name in rel_types:
            related_doc_ids[type_name] = (
                related_docs.filter(type__name=type_name)
                .values_list("document__id", flat=True)
                .distinct()
            )

        # get names of related documents (grouped by type name) and set on output dict
        for [type_name, doc_ids] in related_doc_ids.items():
            tn = slugify(type_name).replace("-", "_")
            outd[f"{tn}_documents"] = ", ".join(
                sorted([str(doc) for doc in Document.objects.filter(id__in=doc_ids)])
            )

        # get names of related events and set on output dict
        related_event_ids = (
            PlaceEventRelation.objects.filter(place__id=place.id)
            .values_list("event__id", flat=True)
            .distinct()
        )
        related_events = Event.objects.filter(id__in=related_event_ids)
        outd["events"] = ", ".join(
            [e.name for e in related_events.order_by("standard_date", "name")]
        )

        # add admin url
        outd[
            "url_admin"
        ] = f"{self.url_scheme}{self.site_domain}/admin/entities/place/{place.id}/change/"

        return outd

from django.db.models.query import Prefetch
from django.utils.text import slugify

from geniza.common.metadata_export import Exporter
from geniza.corpus.dates import standard_date_display
from geniza.corpus.models import Document
from geniza.entities.models import (
    Person,
    PersonDocumentRelation,
    PersonPlaceRelation,
    Place,
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
        "traces_roots_to",
        "home_base",
        "occasional_trips_to",
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

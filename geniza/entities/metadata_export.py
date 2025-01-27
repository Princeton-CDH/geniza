from itertools import groupby
from operator import itemgetter
from time import sleep

from django.contrib.contenttypes.models import ContentType
from django.db.models import F, Value
from django.db.models.query import Prefetch
from django.utils import timezone
from django.utils.text import slugify

from geniza.common.metadata_export import Exporter
from geniza.corpus.dates import standard_date_display
from geniza.corpus.models import Document, DocumentEventRelation, TextBlock
from geniza.entities.models import (
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Event,
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    Place,
    PlaceEventRelation,
    PlacePlaceRelationType,
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
        "content_type__model__in": ["document", "person", "place"],
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


class RelationsExporter(Exporter):
    """
    A subclass of :class:`geniza.common.metadata_export.Exporter` to extract
    reused logic for an export of related objects. Extends
    :meth:`get_export_data_dict` and :meth:`csv_filename`.
    """

    csv_fields = [
        "related_object_type",
        "related_object_id",
        "related_object_name",
        "relationship_type",
        "shared_documents",
    ]

    def csv_filename(self):
        """Generate the appropriate CSV filename for model and time

        :return: Filename string
        :rtype: str
        """
        str_time = timezone.now().strftime("%Y%m%dT%H%M%S")
        obj = super().get_queryset().first()
        model_name = str(self.model.__name__).lower()
        return f"geniza-{slugify(str(obj))}-{model_name}-relations-{str_time}.csv"

    def get_export_data_dict(self, obj):
        """
        For efficiency, the dict is populated in :meth:`get_queryset`,
        via :meth`populate_relation_fields`, as that method allows us to
        retrieve values for multiple related objects of the same type in bulk.
        """
        data_dict = dict(obj)
        model_name = str(self.model.__name__).lower()
        data_dict[f"source_{model_name}"] = str(super().get_queryset().first())
        return data_dict

    def dedupe_related_objects(self, relations):
        """Deduplicate related objects, in case of multiple relationships
        involving the same object; combine into a single row."""
        prev = None
        for rel in sorted(
            relations,
            # sort for easy deduplication
            key=itemgetter(
                "related_object_type",
                "related_object_id",
                "relationship_type_id",
            ),
        ):
            # dedupe items and combine relationship types
            if (
                prev
                and prev["related_object_type"] == rel["related_object_type"]
                and prev["related_object_id"] == rel["related_object_id"]
            ):
                # dedupe type by string matching since we can't match reverse relations by id
                if (
                    rel.get("relationship_type", "").lower()
                    not in prev.get("relationship_type", "").lower()
                ):
                    prev["relationship_type"] += f", {rel['relationship_type']}".lower()
                relations.remove(rel)
            else:
                prev = rel

        return relations


class PersonRelationsExporter(RelationsExporter):
    """
    A subclass of :class:`RelationsExporter` that exports information relating
    to :class:`~geniza.entities.models.Person`, in particular, the related
    objects for a single model instance. Extends :meth:`get_queryset`.
    """

    model = Person
    csv_fields = ["source_person"] + RelationsExporter.csv_fields

    def get_queryset(self):
        """Override get_queryset to get related items for the single item"""
        person = super().get_queryset().first()
        # union querysets to coalesce and normalize heterogenous data types
        relations = (
            person.from_person.values(
                related_object_id=F("from_person"),
                related_object_type=Value("Person"),
                relationship_type_id=F("type"),
                use_converse_typename=Value(True),
            )
            .union(
                person.to_person.values(
                    related_object_id=F("to_person"),
                    related_object_type=Value("Person"),
                    relationship_type_id=F("type"),
                    use_converse_typename=Value(False),
                )
            )
            .union(
                person.personplacerelation_set.values(
                    related_object_id=F("place"),
                    related_object_type=Value("Place"),
                    relationship_type_id=F("type"),
                    use_converse_typename=Value(False),
                )
            )
            .union(
                person.persondocumentrelation_set.values(
                    related_object_id=F("document"),
                    related_object_type=Value("Document"),
                    relationship_type_id=F("type"),
                    use_converse_typename=Value(False),
                )
            )
            .union(
                person.personeventrelation_set.values(
                    related_object_id=F("event"),
                    related_object_type=Value("Event"),
                    # use -1 as this must be int, but there is no relationship
                    # type for event relations
                    relationship_type_id=Value(-1),
                    use_converse_typename=Value(False),
                )
            )
        )
        # populate additional data
        return self.populate_relation_fields(list(relations))

    def populate_relation_fields(self, relations):
        """Helper method called by :meth:`get_queryset` that prefetches
        various fields on related objects, efficiently retrieving their
        data for export in bulk"""

        # the general rule here is: fetch all the related data with a values()
        # queryset, cast as dict (keyed on id) to compute each queryset ahead
        # of time, and access each field value from the dict by id in a loop.

        # use constants for column names for code readability
        ID = "related_object_id"
        TYPE = "related_object_type"
        RTID = "relationship_type_id"

        # use single query to get names for people and places
        related_people = [r[ID] for r in relations if r[TYPE] == "Person"]
        related_places = [r[ID] for r in relations if r[TYPE] == "Place"]
        names = list(
            Name.objects.filter(
                object_id__in=[*related_people, *related_places],
                primary=True,
            ).values("object_id", "name", "content_type")
        )
        pers_contenttype_id = ContentType.objects.get_for_model(Person).pk
        place_contenttype_id = ContentType.objects.get_for_model(Place).pk

        # for people, places, documents: use single query each to get relation type names
        person_relation_types = PersonPersonRelationType.objects.filter(
            id__in=[r[RTID] for r in relations if r[TYPE] == "Person"]
        ).values("id", "name", "converse_name")
        person_relation_typedict = {t["id"]: t for t in person_relation_types}
        place_relation_types = PersonPlaceRelationType.objects.filter(
            id__in=[r[RTID] for r in relations if r[TYPE] == "Place"]
        ).values("id", "name")
        place_relation_typedict = {t["id"]: t["name"] for t in place_relation_types}
        doc_relation_types = PersonDocumentRelationType.objects.filter(
            id__in=[r[RTID] for r in relations if r[TYPE] == "Document"]
        ).values("id", "name")
        doc_relation_typedict = {t["id"]: t["name"] for t in doc_relation_types}

        # get shared documents with People, Places, and Events
        related_docs = [r[ID] for r in relations if r[TYPE] == "Document"]
        related_events = [r[ID] for r in relations if r[TYPE] == "Event"]
        shared_person_docs = list(
            PersonDocumentRelation.objects.filter(
                document__id__in=related_docs, person__id__in=related_people
            ).values("document__id", "person__id")
        )
        shared_person_docs = sorted(shared_person_docs, key=itemgetter("person__id"))
        persondocs_dict = {
            k: [d["document__id"] for d in v]
            for k, v in groupby(shared_person_docs, key=itemgetter("person__id"))
        }
        shared_place_docs = list(
            DocumentPlaceRelation.objects.filter(
                document__id__in=related_docs, place__id__in=related_places
            ).values("document__id", "place__id")
        )
        shared_place_docs = sorted(shared_place_docs, key=itemgetter("place__id"))
        placedocs_dict = {
            k: [d["document__id"] for d in v]
            for k, v in groupby(shared_place_docs, key=itemgetter("place__id"))
        }
        shared_event_docs = list(
            DocumentEventRelation.objects.filter(
                document__id__in=related_docs, event__id__in=related_events
            ).values("document__id", "event__id")
        )
        shared_event_docs = sorted(shared_event_docs, key=itemgetter("event__id"))
        eventdocs_dict = {
            k: [d["document__id"] for d in v]
            for k, v in groupby(shared_event_docs, key=itemgetter("event__id"))
        }

        # to get Document names, need TextBlocks and Fragments
        docs = Document.objects.prefetch_related(
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment",
                ).prefetch_related(
                    "fragment__textblock_set",
                    "fragment__textblock_set__document",
                ),
            )
        ).filter(id__in=related_docs)
        docs_dict = {d.id: str(d) for d in docs}

        # get Event names
        events = Event.objects.filter(id__in=related_events).values("id", "name")
        events_dict = {e["id"]: e["name"] for e in events}

        # loop through all relations, update with additional data, and dedupe
        # use all precomputed query results to populate additional data per obj
        for rel in sorted(
            relations,
            # sort for deduplication
            key=itemgetter(TYPE, ID, RTID),
        ):
            if rel[TYPE] == "Person":
                # get person name, relationship type from precomputed querysets
                filtered_names = filter(
                    lambda n: n.get("object_id") == rel[ID]
                    and n.get("content_type") == pers_contenttype_id,
                    names,
                )
                rel_type = person_relation_typedict.get(rel[RTID])
                rel.update(
                    {
                        "related_object_name": next(filtered_names).get("name"),
                        "relationship_type": (
                            # handle converse type names for self-referential relationships
                            rel_type.get("converse_name")
                            if rel["use_converse_typename"]
                            and rel_type.get("converse_name")
                            # use name if should use name, or converse does not exist
                            else rel_type.get("name")
                        ),
                        "shared_documents": ", ".join(
                            [
                                docs_dict.get(doc_id)
                                for doc_id in persondocs_dict.get(rel[ID], [])
                            ]
                        ),
                    }
                )
            elif rel[TYPE] == "Place":
                # get place name, relationship type from precomputed querysets
                filtered_names = filter(
                    lambda n: n.get("object_id") == rel[ID]
                    and n.get("content_type") == place_contenttype_id,
                    names,
                )
                rel.update(
                    {
                        "related_object_name": next(filtered_names).get("name"),
                        "relationship_type": place_relation_typedict.get(rel[RTID]),
                        "shared_documents": ", ".join(
                            [
                                docs_dict.get(doc_id)
                                for doc_id in placedocs_dict.get(rel[ID], [])
                            ]
                        ),
                    }
                )
            elif rel[TYPE] == "Document":
                # get doc name, doc relation type name from precomputed querysets
                rel.update(
                    {
                        "related_object_name": docs_dict.get(rel[ID]),
                        "relationship_type": doc_relation_typedict.get(rel[RTID]),
                    }
                )
            elif rel[TYPE] == "Event":
                # get event name from precomputed names queryset; relation type
                rel.update(
                    {
                        "related_object_name": events_dict.get(rel[ID]),
                        "shared_documents": ", ".join(
                            [
                                docs_dict.get(doc_id)
                                for doc_id in eventdocs_dict.get(rel[ID], [])
                            ]
                        ),
                    }
                )
                # relationship type is not used for events

        return sorted(
            self.dedupe_related_objects(relations),
            # sort by object type, then name
            key=lambda r: (r[TYPE], slugify(r["related_object_name"])),
        )


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
        "related_documents_count",
        "related_people_count",
        "related_events_count",
        "url",
    ]

    # queryset filter for content types included in this export
    content_type_filter = {
        "content_type__app_label__in": ["entities", "corpus"],
        "content_type__model__in": ["document", "person", "place", "event"],
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
                "personplacerelation_set",
                "documentplacerelation_set",
                "placeeventrelation_set",
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
        # get number of related documents
        related_docs_count = (
            DocumentPlaceRelation.objects.filter(place__id=place.id)
            .values_list("document__id", flat=True)
            .distinct()
            .count()
        )
        # get number of related people
        related_people_count = (
            PersonPlaceRelation.objects.filter(place__id=place.id)
            .values_list("person__id", flat=True)
            .distinct()
            .count()
        )
        # get number of related events
        related_events_count = (
            PlaceEventRelation.objects.filter(place__id=place.id)
            .values_list("event__id", flat=True)
            .distinct()
            .count()
        )

        outd = {
            "name": str(place),
            "name_variants": ", ".join(
                sorted([n.name for n in place.names.non_primary()])
            ),
            "coordinates": place.coordinates,
            "notes": place.notes,
            "related_documents_count": related_docs_count,
            "related_people_count": related_people_count,
            "related_events_count": related_events_count,
            "url": place.permalink,
        }

        return outd


class AdminPlaceExporter(PublicPlaceExporter):
    csv_fields = PublicPlaceExporter.csv_fields + [
        "url_admin",
    ]

    def get_export_data_dict(self, place):
        """
        Adding certain fields to PublicPlaceExporter.get_export_data_dict that are admin-only.
        """
        outd = super().get_export_data_dict(place)

        # add admin url
        outd[
            "url_admin"
        ] = f"{self.url_scheme}{self.site_domain}/admin/entities/place/{place.id}/change/"

        return outd


class PlaceRelationsExporter(RelationsExporter):
    """
    A subclass of :class:`RelationsExporter` that exports information relating
    to :class:`~geniza.entities.models.Place`, in particular, the related
    objects for a single model instance. Extends :meth:`get_queryset`.
    """

    model = Place
    csv_fields = (
        ["source_place"]
        + RelationsExporter.csv_fields
        + [
            "related_object_date",  # only events and documents should get dates
            "relationship_notes",
        ]
    )

    def get_queryset(self):
        """Override get_queryset to get related items for the single item"""
        place = super().get_queryset().first()
        # union querysets to coalesce and normalize heterogenous data types
        relations = (
            place.place_a.values(
                related_object_id=F("place_a"),
                related_object_type=Value("Place"),
                relationship_type_id=F("type"),
                relationship_notes=F("notes"),
                use_converse_typename=Value(True),
            )
            .union(
                place.place_b.values(
                    related_object_id=F("place_b"),
                    related_object_type=Value("Place"),
                    relationship_type_id=F("type"),
                    relationship_notes=F("notes"),
                    use_converse_typename=Value(False),
                )
            )
            .union(
                place.personplacerelation_set.values(
                    related_object_id=F("person"),
                    related_object_type=Value("Person"),
                    relationship_type_id=F("type"),
                    relationship_notes=F("notes"),
                    use_converse_typename=Value(False),
                )
            )
            .union(
                place.documentplacerelation_set.values(
                    related_object_id=F("document"),
                    related_object_type=Value("Document"),
                    relationship_type_id=F("type"),
                    relationship_notes=F("notes"),
                    use_converse_typename=Value(False),
                )
            )
            .union(
                place.placeeventrelation_set.values(
                    related_object_id=F("event"),
                    related_object_type=Value("Event"),
                    # use -1 as this must be int, but there is no relationship
                    # type for event relations
                    relationship_type_id=Value(-1),
                    relationship_notes=F("notes"),
                    use_converse_typename=Value(False),
                )
            )
        )
        # populate additional data
        return self.populate_relation_fields(list(relations))

    def populate_relation_fields(self, relations):
        """Helper method called by :meth:`get_queryset` that prefetches
        various fields on related objects, efficiently retrieving their
        data for export in bulk"""

        # the general rule here is: fetch all the related data with a values()
        # queryset, cast as dict (keyed on id) to compute each queryset ahead
        # of time, and access each field value from the dict by id in a loop.

        # use constants for column names for code readability
        ID = "related_object_id"
        TYPE = "related_object_type"
        RTID = "relationship_type_id"

        # use single query to get names for people and places
        related_people = [r[ID] for r in relations if r[TYPE] == "Person"]
        related_places = [r[ID] for r in relations if r[TYPE] == "Place"]
        names = list(
            Name.objects.filter(
                object_id__in=[*related_people, *related_places],
                primary=True,
            ).values("object_id", "name", "content_type")
        )
        pers_contenttype_id = ContentType.objects.get_for_model(Person).pk
        place_contenttype_id = ContentType.objects.get_for_model(Place).pk

        # for people, places, documents: use single query each to get relation type names
        person_relation_types = PersonPlaceRelationType.objects.filter(
            id__in=[r[RTID] for r in relations if r[TYPE] == "Person"]
        ).values("id", "name")
        person_relation_typedict = {t["id"]: t for t in person_relation_types}
        place_relation_types = PlacePlaceRelationType.objects.filter(
            id__in=[r[RTID] for r in relations if r[TYPE] == "Place"]
        ).values("id", "name")
        place_relation_typedict = {t["id"]: t for t in place_relation_types}
        doc_relation_types = DocumentPlaceRelationType.objects.filter(
            id__in=[r[RTID] for r in relations if r[TYPE] == "Document"]
        ).values("id", "name")
        doc_relation_typedict = {t["id"]: t["name"] for t in doc_relation_types}

        # get shared documents with People, Places, and Events
        related_docs = [r[ID] for r in relations if r[TYPE] == "Document"]
        related_events = [r[ID] for r in relations if r[TYPE] == "Event"]
        shared_person_docs = list(
            PersonDocumentRelation.objects.filter(
                document__id__in=related_docs, person__id__in=related_people
            ).values("document__id", "person__id")
        )
        shared_person_docs = sorted(shared_person_docs, key=itemgetter("person__id"))
        persondocs_dict = {
            k: [d["document__id"] for d in v]
            for k, v in groupby(shared_person_docs, key=itemgetter("person__id"))
        }
        shared_place_docs = list(
            DocumentPlaceRelation.objects.filter(
                document__id__in=related_docs, place__id__in=related_places
            ).values("document__id", "place__id")
        )
        shared_place_docs = sorted(shared_place_docs, key=itemgetter("place__id"))
        placedocs_dict = {
            k: [d["document__id"] for d in v]
            for k, v in groupby(shared_place_docs, key=itemgetter("place__id"))
        }
        shared_event_docs = list(
            DocumentEventRelation.objects.filter(
                document__id__in=related_docs, event__id__in=related_events
            ).values("document__id", "event__id")
        )
        shared_event_docs = sorted(shared_event_docs, key=itemgetter("event__id"))
        eventdocs_dict = {
            k: [d["document__id"] for d in v]
            for k, v in groupby(shared_event_docs, key=itemgetter("event__id"))
        }

        # to get Document names, need TextBlocks and Fragments.
        # to get Document dates, need Datings.
        docs = Document.objects.prefetch_related(
            "dating_set",
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment",
                ).prefetch_related(
                    "fragment__textblock_set",
                    "fragment__textblock_set__document",
                ),
            ),
        ).filter(id__in=related_docs)

        # use standard date display for full possible document date range
        docs_dict = {
            d.id: {
                "name": str(d),
                "date": standard_date_display(
                    "/".join([dr.isoformat() for dr in d.dating_range() if dr])
                ),
            }
            for d in docs
        }

        # get Event names
        events = Event.objects.filter(id__in=related_events)
        events_dict = {
            e.id: {
                "name": e.name,
                "date": standard_date_display(e.documents_date_range),
            }
            for e in events
        }

        # loop through all relations, update with additional data, and dedupe
        # use all precomputed query results to populate additional data per obj
        for rel in relations:
            if rel[TYPE] == "Person":
                # get person name, relationship type from precomputed querysets
                filtered_names = filter(
                    lambda n: n.get("object_id") == rel[ID]
                    and n.get("content_type") == pers_contenttype_id,
                    names,
                )
                rel_type = person_relation_typedict.get(rel[RTID])
                rel.update(
                    {
                        "related_object_name": next(filtered_names).get("name"),
                        "relationship_type": rel_type.get("name"),
                        "shared_documents": ", ".join(
                            [
                                docs_dict.get(doc_id, {}).get("name")
                                for doc_id in persondocs_dict.get(rel[ID], [])
                            ]
                        ),
                    }
                )
            elif rel[TYPE] == "Place":
                # get place name, relationship type from precomputed querysets
                filtered_names = filter(
                    lambda n: n.get("object_id") == rel[ID]
                    and n.get("content_type") == place_contenttype_id,
                    names,
                )
                rel_type = place_relation_typedict.get(rel[RTID])
                rel.update(
                    {
                        "related_object_name": next(filtered_names).get("name"),
                        "relationship_type": (
                            # handle converse type names for self-referential relationships
                            rel_type.get("converse_name")
                            if rel["use_converse_typename"]
                            and rel_type.get("converse_name")
                            # use name if should use name, or converse does not exist
                            else rel_type.get("name")
                        ),
                        "shared_documents": ", ".join(
                            [
                                docs_dict.get(doc_id, {}).get("name")
                                for doc_id in placedocs_dict.get(rel[ID], [])
                            ]
                        ),
                    }
                )
            elif rel[TYPE] == "Document":
                # get doc name, doc relation type, date from precomputed querysets
                doc = docs_dict.get(rel[ID], {})
                rel.update(
                    {
                        "related_object_name": doc.get("name"),
                        "relationship_type": doc_relation_typedict.get(rel[RTID]),
                        "related_object_date": doc.get("date"),
                    }
                )
            elif rel[TYPE] == "Event":
                # get event name, date from precomputed queryset
                evt = events_dict.get(rel[ID], {})
                rel.update(
                    {
                        "related_object_name": evt.get("name"),
                        "related_object_date": evt.get("date"),
                        "shared_documents": ", ".join(
                            [
                                docs_dict.get(doc_id, {}).get("name")
                                for doc_id in eventdocs_dict.get(rel[ID], {})
                            ]
                        ),
                    }
                )

        return sorted(
            self.dedupe_related_objects(relations),
            # sort by object type, then name
            key=lambda r: (r["related_object_type"], slugify(r["related_object_name"])),
        )

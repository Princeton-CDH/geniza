from collections import defaultdict

from django.utils.text import slugify


def document_entity_index_data(doc):
    """Entity-related index data for a :class:`~geniza.corpus.models.Document`"""
    # get related place IDs for join query on document dates
    places = list(doc.documentplacerelation_set.values_list("place", flat=True))
    return {
        "people_count_i": doc.persondocumentrelation_set.count(),
        "places_count_i": len(places),
        "places_ids_ss": [f"place.{id}" for id in places],
    }


def merge_document_entities(primary, merged):
    """Reassociate people, places, and events when merging documents"""
    primary._merge_entities(merged, "person", "persondocumentrelation_set")
    primary._merge_entities(merged, "place", "documentplacerelation_set")
    # DocumentEventRelation doesn't have a type field
    primary._merge_entities(
        merged, "event", "documenteventrelation_set", has_type=False
    )


def document_place_export_fields():
    """Document export columns, one per :class:`DocumentPlaceRelationType`"""
    from geniza.entities.models import DocumentPlaceRelationType

    return [
        slugify(dpr_type.name).replace("-", "_")
        for dpr_type in DocumentPlaceRelationType.objects.order_by("name")
    ]


def document_place_export_data(doc):
    """Names of related places for a document, grouped by relation type"""
    places_by_type = defaultdict(set)
    for rel in doc.documentplacerelation_set.all():
        places_by_type[rel.type.name].add(str(rel.place))
    return {
        slugify(type_name).replace("-", "_"): ", ".join(sorted(places))
        for type_name, places in places_by_type.items()
    }

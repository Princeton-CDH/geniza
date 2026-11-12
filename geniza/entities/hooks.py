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

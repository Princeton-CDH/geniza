from django.apps import AppConfig


class EntitiesConfig(AppConfig):
    name = "geniza.entities"

    def ready(self):
        from geniza.corpus.models import Document
        from geniza.entities.hooks import (
            document_entity_index_data,
            merge_document_entities,
        )

        Document.extra_prefetches.extend(
            ["persondocumentrelation_set", "documentplacerelation_set"]
        )
        Document.index_data_hooks.append(document_entity_index_data)
        Document.merge_hooks.append(merge_document_entities)

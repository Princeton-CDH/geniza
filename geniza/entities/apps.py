from django.apps import AppConfig


class EntitiesConfig(AppConfig):
    name = "geniza.entities"

    def ready(self):
        from geniza.corpus.metadata_export import DocumentExporter
        from geniza.corpus.models import Document
        from geniza.entities.hooks import (
            document_entity_index_data,
            document_place_export_data,
            document_place_export_fields,
            merge_document_entities,
        )

        Document.extra_prefetches.extend(
            ["persondocumentrelation_set", "documentplacerelation_set"]
        )
        Document.index_data_hooks.append(document_entity_index_data)
        Document.merge_hooks.append(merge_document_entities)

        DocumentExporter.extra_prefetches.extend(
            [
                "documentplacerelation_set__type",
                "documentplacerelation_set__place",
            ]
        )
        DocumentExporter.extra_field_hooks.append(document_place_export_fields)
        DocumentExporter.export_data_hooks.append(document_place_export_data)

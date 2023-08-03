from django.apps import AppConfig
from django.db.models.signals import m2m_changed


class EntitiesConfig(AppConfig):
    name = "geniza.entities"

    def ready(self):
        # attach m2m_changed signal for person-document relations
        from geniza.entities.models import PersonSignalHandlers

        m2m_changed.connect(
            PersonSignalHandlers.person_document_relation_changed,
            sender="entities.PersonDocumentRelation",
        )
        return super().ready()

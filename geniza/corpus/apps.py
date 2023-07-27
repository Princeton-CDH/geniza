from django.apps import AppConfig
from django.db.models.signals import m2m_changed, pre_save


class CorpusAppConfig(AppConfig):
    name = "geniza.corpus"

    def ready(self):
        # import and connect signal handlers for Solr indexing
        from parasolr.django.signals import IndexableSignalHandler

        from geniza.corpus.models import TagSignalHandlers

        pre_save.connect(TagSignalHandlers.unidecode_tag, sender="taggit.Tag")
        m2m_changed.connect(
            TagSignalHandlers.tagged_item_change, sender="taggit.TaggedItem"
        )
        return super().ready()

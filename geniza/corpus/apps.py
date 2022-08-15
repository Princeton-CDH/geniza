from django.apps import AppConfig
from django.db.models.signals import pre_save


class CorpusAppConfig(AppConfig):
    name = "geniza.corpus"

    def ready(self):
        # import and connect signal handlers for Solr indexing
        from parasolr.django.signals import IndexableSignalHandler

        from geniza.corpus.models import TagSignalHandlers

        pre_save.connect(TagSignalHandlers.unidecode_tag, sender="taggit.Tag")
        return super().ready()

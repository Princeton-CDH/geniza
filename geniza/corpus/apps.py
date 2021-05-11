from django.apps import AppConfig


class CorpusAppConfig(AppConfig):
    name = 'geniza.corpus'

    def ready(self):
        # import and connect signal handlers for Solr indexing
        from parasolr.django.signals import IndexableSignalHandler

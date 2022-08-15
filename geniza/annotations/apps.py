from django.apps import AppConfig
from django.db.models.signals import post_save


class AnnotationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "geniza.annotations"

    def ready(self):
        from geniza.annotations.signals import get_or_create_footnote

        post_save.connect(get_or_create_footnote, sender="annotations.Annotation")
        return super().ready()

from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class AnnotationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "geniza.annotations"

    def ready(self):
        from geniza.annotations.signals import create_or_delete_footnote

        post_save.connect(create_or_delete_footnote, sender="annotations.Annotation")
        post_delete.connect(create_or_delete_footnote, sender="annotations.Annotation")
        return super().ready()

from django.apps import AppConfig
from django.db.models.signals import post_save


class AnnotationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "geniza.annotations"

    def ready(self):
        from geniza.annotations.signals import update_footnote

        post_save.connect(update_footnote, sender="annotations.Annotation")
        return super().ready()

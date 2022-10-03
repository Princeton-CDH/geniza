from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_delete, post_save


class AnnotationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "geniza.annotations"

    def ready(self):
        from geniza.annotations.signals import connect_signal_handlers

        connect_signal_handlers()
        return super().ready()

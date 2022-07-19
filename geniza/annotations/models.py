import uuid

from django.db import models
from django.urls import reverse

from geniza.common.utils import absolutize_url


class Annotation(models.Model):
    #: annotation id
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    #: json content of the annotation
    content = models.JSONField()
    #: optional canonical identifier, for annotations imported from another source
    canonical = models.CharField(max_length=255, blank=True)
    #: uri of annotation when imported from another copy (optional)
    via = models.URLField(blank=True)

    def __repr__(self):
        return f"Annotation(id={self.id})"

    def get_absolute_url(self):
        return reverse("annotations:annotation", kwargs={"pk": self.pk})

    def uri(self):
        return absolutize_url(self.get_absolute_url())

    def compile(self):
        anno = {
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "id": self.uri(),
            "type": "Annotation",
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
        }
        if self.canonical:
            anno["canonical"] = self.canonical
        if self.via:
            anno["via"] = self.via
        # FIXME: don't let json values override the content
        anno.update(self.content)
        return anno

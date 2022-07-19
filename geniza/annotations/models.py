import uuid

from django.contrib import admin
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

    class Meta:
        # by default, order by creation time
        ordering = ["created"]

    def __repr__(self):
        return f"Annotation(id={self.id})"

    def get_absolute_url(self):
        return reverse("annotations:annotation", kwargs={"pk": self.pk})

    @admin.display(
        ordering="id",
        description="URI",
    )
    def uri(self):
        return absolutize_url(self.get_absolute_url())

    def set_content(self, data):
        """Set or update annotation content and model fields."""
        # remove any values tracked on the model; redundant in json field
        for val in ["id", "created", "modified", "@context", "type"]:
            if val in data:
                del data[val]

        # store via and canonical if set; error if set and different
        if "canonical" in data:
            if self.canonical and self.canonical != data["canonical"]:
                # TODO: custom exception?
                raise ValueError("canonical id differs")
            self.canonical = data["canonical"]
            del data["canonical"]
        if "via" in data:
            if self.via and self.via != data["via"]:
                raise ValueError("canonical id differs")
            self.via = data["via"]
            del data["via"]

        print("setting content, data is :")
        print(data)

        self.content = data

    def compile(self):
        """Combine annotation data and return as a dictionary that
        can be serialized as JSON."""

        # define these first, so values will be listed in a sensible order
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
        # make a copy of the base annotation data
        base_anno = anno.copy()
        # update with the rest of the annotation content
        anno.update(self.content)
        # overwrite with the base annotation data in case of any collisions
        # between content and model fields
        anno.update(base_anno)
        return anno

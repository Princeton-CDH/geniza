import pytest
from django.urls import reverse

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
from geniza.footnotes.models import Source, SourceType


@pytest.fixture
def annotation(db):
    document = Document.objects.create()
    book = SourceType.objects.get(type="Book")
    source = Source.objects.create(
        title_en="The C Programming Language", source_type=book
    )
    annotation = Annotation.objects.create(
        content={
            "body": [{"value": "Test annotation"}],
            "target": {
                "source": {
                    "partOf": {
                        "id": reverse(
                            "corpus:document-manifest", kwargs={"pk": document.pk}
                        )
                    }
                }
            },
            "dc:source": source.uri,
        }
    )
    return annotation

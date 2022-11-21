import pytest
from django.urls import reverse

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source, SourceType


@pytest.fixture
def annotation(db):
    document = Document.objects.create()
    book = SourceType.objects.get(type="Book")
    source = Source.objects.create(
        title_en="The C Programming Language", source_type=book
    )
    footnote = Footnote.objects.create(
        source=source, content_object=document, doc_relation=Footnote.DIGITAL_EDITION
    )
    annotation = Annotation.objects.create(
        footnote=footnote,
        content={
            "body": [{"value": "Test annotation"}],
            "target": {
                "source": {
                    "id": "http://ex.co/iiif/canvas/1",
                }
            },
        },
    )
    return annotation

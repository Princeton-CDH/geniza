import pytest
from django.urls import reverse

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source, SourceType


@pytest.fixture
def annotation(db, document, source):
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
            "motivation": ["sc:supplementing", "transcribing"],
        },
    )
    return annotation


@pytest.fixture
def translation_annotation(db, document, source):
    footnote = Footnote.objects.create(
        source=source,
        content_object=document,
        doc_relation=Footnote.DIGITAL_TRANSLATION,
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
            "motivation": ["sc:supplementing", "translating"],
        },
    )
    return annotation


@pytest.fixture
def annotation_json(document, source):
    return {
        "body": [{"value": "Test annotation"}],
        "target": {
            "source": {
                "partOf": {
                    "id": reverse(
                        "corpus-uris:document-manifest",
                        kwargs={"pk": document.pk},
                    )
                }
            }
        },
        "motivation": ["sc:supplementing", "transcribing"],
        "dc:source": source.uri,
    }


@pytest.fixture
def malformed_annotations(annotation, annotation_json):
    return [
        {},  # no content
        {**annotation.content},  # missing manifest and source URI
        {
            **annotation.content,
            "target": annotation_json["target"],  # missing only source
        },
        {
            **annotation.content,
            "dc:source": annotation_json["dc:source"],  # missing only manifest
        },
        {
            **annotation_json,
            "dc:source": "bad",  # bad source, good manifest
            "target": annotation_json["target"],
        },
    ]

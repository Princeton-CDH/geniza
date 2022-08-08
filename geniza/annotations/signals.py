from geniza.annotations.models import Annotation
from geniza.corpus.models import Document


def update_footnote(instance, **kwargs):
    """On Annotation save or delete, update related footnote's has_transcription field
    and trigger a reindex of related documents (via footnote save)"""
    created = kwargs.get("created")
    deleted = created is None
    # get canvas URI from annotation content and match it to Documents
    canvas_uri = instance.content["target"]["source"]["id"]
    docs = Document.objects.filter(fragments__manifest__canvases__uri=canvas_uri)
    # get source URI from annotation content and match it to document's Footnotes
    source_uri = instance.content["dc:source"]
    source_pk = int(source_uri.split("/")[-1])
    # get other annotations on this canvas and source
    other_annotations_exist = (
        Annotation.objects.exclude(pk=instance.pk)
        .filter(
            content__target__source__id=canvas_uri,
            content__contains={"dc:source": source_uri},
        )
        .count()
        > 0
    )
    # update footnote(s)
    for doc in docs:
        footnotes = doc.footnotes.filter(source__pk=source_pk)
        for footnote in footnotes:
            if deleted and footnote.has_transcription and not other_annotations_exist:
                footnote.has_transcription = False
            elif not footnote.has_transcription and created:
                footnote.has_transcription = True
            footnote.save()  # ensure footnote is saved regardless for reindexing purposes

from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote


def update_footnote(instance, **kwargs):
    """On Annotation save or delete, update related footnote's has_transcription field"""
    created = kwargs.get("created")
    deleted = created is None
    # NOTE: Do we need to trigger a reindex on footnotes if not created or deleted, i.e. annotation
    # text changed and thus we need to reindex footnote's content?
    if created or deleted:
        # get canvas URI from annotation content and match it to Documents
        canvas_uri = instance.content["target"]["source"]["id"]
        docs = Document.objects.filter(fragments__manifest__canvases__uri=canvas_uri)
        # get source URI from annotation content and match it to document's Footnotes
        source_uri = instance.content["dc:source"]
        source_pk = int(source_uri.split("/")[-1])
        # update footnote(s)
        for doc in docs:
            footnotes = doc.footnotes.filter(source__pk=source_pk)
            for footnote in footnotes:
                if footnote.has_transcription and deleted:
                    footnote.has_transcription = False
                elif not footnote.has_transcription and created:
                    footnote.has_transcription = True
                footnote.save()

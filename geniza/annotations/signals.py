from django.conf import settings
from django.contrib.admin.models import ADDITION, DELETION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source


def create_or_delete_footnote(instance, **kwargs):
    """On Annotation save, create digital edition Footnote if necessary.
    On Annotation delete, if it's the only Annotation for the corresponding Footnote,
    delete the Footnote."""
    # get manifest uri from annotation content and match it to a Document
    manifest_uri = instance.content["target"]["source"]["partOf"]["id"]
    source_uri = instance.content["dc:source"]
    document = Document.from_manifest_uri(manifest_uri)
    # if deleted, created is None; if updated but not deleted, created is False
    deleted = kwargs.get("created") is None

    try:
        # try to get a DIGITAL_EDITION footnote for this source and document
        footnote = document.footnotes.get(
            source=Source.from_uri(source_uri),
            doc_relation__contains=Footnote.DIGITAL_EDITION,
        )
        # if this Annotation was deleted and no others exist on this source and document,
        # delete the footnote too
        if (
            deleted
            and not Annotation.objects.filter(
                content__target__source__partOf__id=manifest_uri,
                content__contains={"dc:source": source_uri},
            ).exists()
        ):
            footnote.delete()
            log_footnote_action(footnote, DELETION)
    except Footnote.DoesNotExist:
        if not deleted:
            # create the DIGITAL_EDITION footnote
            footnote = document.footnotes.create(
                source=Source.from_uri(source_uri),
                doc_relation=[Footnote.DIGITAL_EDITION],
            )
            log_footnote_action(footnote, ADDITION)


def log_footnote_action(footnote, action_flag):
    created_or_deleted = "created" if action_flag == ADDITION else "deleted"
    LogEntry.objects.log_action(
        user_id=User.objects.get(username=settings.SCRIPT_USERNAME).id,
        content_type_id=ContentType.objects.get_for_model(Footnote).pk,
        object_id=footnote.pk,
        object_repr=str(footnote),
        action_flag=action_flag,
        change_message=f"Footnote automatically {created_or_deleted} via {created_or_deleted} annotation.",
    )

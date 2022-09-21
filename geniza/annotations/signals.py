import logging
import time

from django.conf import settings
from django.contrib.admin.models import ADDITION, DELETION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save
from parasolr.django.indexing import ModelIndexable

from geniza.annotations.models import Annotation
from geniza.corpus.annotation_export import AnnotationExporter
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source

logger = logging.getLogger(__name__)


def create_or_delete_footnote(instance, **kwargs):
    """On Annotation save, create digital edition Footnote if necessary.
    On Annotation delete, if it's the only Annotation for the corresponding Footnote,
    delete the Footnote."""
    # get manifest uri from annotation content and match it to a Document

    try:
        manifest_uri = instance.target_source_manifest_id
        source_uri = instance.content["dc:source"]
    except KeyError:
        # annotations created from tahqiq should have these;
        # if not present, bail out
        # (likely only happening in unit tests)
        return

    # TODO: can we get ids without loading source/doc from db?

    # if we don't have identifiers for both source and document, bail out
    if not source_uri or not manifest_uri:
        return

    source = Source.from_uri(source_uri)
    document = Document.from_manifest_uri(manifest_uri)
    # if deleted, created is None; if updated but not deleted, created is False
    deleted = kwargs.get("created") is None
    updated = kwargs.get("created") is False

    try:
        # try to get a DIGITAL_EDITION footnote for this source and document
        footnote = document.digital_editions().get(source=source)
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

            logger.debug("Deleting digital edition footnote (last annotation deleted)")
        # if this annotation was just updated, reindex document
        elif updated:
            start = time.time()
            ModelIndexable.index_items([document])
            logger.debug(
                "Reindexing document %s (existing annotation updated): %f sec"
                % (document.pk, time.time() - start)
            )

    except Footnote.DoesNotExist:
        if not deleted:
            # create the DIGITAL_EDITION footnote
            footnote = document.footnotes.create(
                source=source,
                doc_relation=[Footnote.DIGITAL_EDITION],
            )
            log_footnote_action(footnote, ADDITION)

            logger.debug("Creating new digital edition footnote (new annotation)")

    # update annotation backup if configured (don't run for tests!)
    if hasattr(settings, "ANNOTATION_BACKUP_PATH"):
        start = time.time()
        AnnotationExporter(pgpids=[document.pk], push_changes=False).export()
        logger.debug(
            "Updated annotation backup for document %s: %f sec"
            % (document.pk, time.time() - start)
        )


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


def connect_signal_handlers():
    post_save.connect(create_or_delete_footnote, sender=Annotation)
    post_delete.connect(create_or_delete_footnote, sender=Annotation)


def disconnect_signal_handlers():
    post_save.disconnect(create_or_delete_footnote, sender=Annotation)
    post_delete.disconnect(create_or_delete_footnote, sender=Annotation)

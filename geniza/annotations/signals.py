import logging
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.models import ADDITION, DELETION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save
from django.utils import timezone
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

    # if we don't have identifiers for both source and document, bail out
    if not source_uri or not manifest_uri:
        return

    # get ids for referenced Source and Document
    source_id = Source.id_from_uri(source_uri)
    document_id = Document.id_from_manifest_uri(manifest_uri)

    document_contenttype = ContentType.objects.get_for_model(Document)
    # if deleted, created is None; if updated but not deleted, created is False
    deleted = kwargs.get("created") is None
    updated = kwargs.get("created") is False

    try:
        # try to get a DIGITAL_EDITION footnote for this source and document
        footnote = Footnote.objects.get(
            doc_relation=[Footnote.DIGITAL_EDITION],
            source__pk=source_id,
            content_type=document_contenttype,
            object_id=document_id,
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

            logger.debug("Deleting digital edition footnote (last annotation deleted)")
        # if this annotation was just updated, reindex document
        elif updated:
            start = time.time()
            ModelIndexable.index_items([Document.objects.get(pk=document_id)])
            logger.debug(
                "Reindexing document %s (existing annotation updated): %f sec"
                % (document_id, time.time() - start)
            )

    except Footnote.DoesNotExist:
        if not deleted:
            # create the DIGITAL_EDITION footnote
            source = Source.objects.get(pk=source_id)
            footnote = Footnote.objects.create(
                source=source,
                doc_relation=[Footnote.DIGITAL_EDITION],
                object_id=document_id,
                content_type=document_contenttype,
            )
            log_footnote_action(footnote, ADDITION)
            logger.debug("Creating new digital edition footnote (new annotation)")

    # disable github backup on signal, not thread safe
    # # update annotation backup if configured (don't run for tests!)
    # if getattr(settings, "ANNOTATION_BACKUP_PATH", None):
    #     backup_annotation(document.pk, instance)


def backup_annotation(document_id, annotation):
    """update document transcription backup on annotation save"""
    start = time.time()
    now = timezone.now()
    # get log entry to give co-author credit on the commit
    # to the user who made the change (when possible)

    # look for log entries on this object, ordered by most recent
    # limit to log entries in the last ten seconds to avoid
    # picking up the wrong log entry; sort most recent first
    last_log_entry = (
        LogEntry.objects.filter(
            object_id=annotation.pk,
            content_type_id=ContentType.objects.get_for_model(annotation.__class__).pk,
            action_time__gte=(now - timedelta(seconds=10)),
        )
        .order_by("-action_time")
        .first()
    )

    # if a log entry is found, pass in user to track as co-author
    coauthors = []
    if last_log_entry:
        # export code handles check for profile / github coauthor email
        coauthors = [last_log_entry.user]

    # skip pushing changes, since it could delay response
    AnnotationExporter(
        pgpids=[document_id], push_changes=False, modifying_users=coauthors
    ).export()
    logger.debug(
        "Updated annotation backup for document %s: %f sec"
        % (document_id, time.time() - start)
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

import logging
import time
from datetime import timedelta

from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from geniza.corpus.annotation_export import AnnotationExporter

logger = logging.getLogger(__name__)


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

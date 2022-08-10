from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source


def update_footnote(instance, **kwargs):
    """On Annotation save, update related footnote's doc_relation field if necessary"""
    # get pgpid from annotation content and match it to a Document
    document = Document.from_manifest_uri(
        instance.content["target"]["source"]["partOf"]["id"]
    )

    # create or update footnote
    try:
        # if the footnote exists but is an EDITION, make it also a DIGITAL_EDITION
        footnote = document.footnotes.exclude(
            doc_relation__contains=Footnote.DIGITAL_EDITION
        ).get(
            source=Source.from_uri(instance.content["dc:source"]),
            doc_relation__contains=Footnote.EDITION,
        )
        footnote.doc_relation.append(Footnote.DIGITAL_EDITION)
        footnote.save()
    except Footnote.DoesNotExist:
        # create the DIGITAL_EDITION footnote (unless it already exists)
        footnote, created = document.footnotes.get_or_create(
            source=Source.from_uri(instance.content["dc:source"]),
            doc_relation__contains=Footnote.DIGITAL_EDITION,
        )
        if created:
            footnote.doc_relation = [Footnote.DIGITAL_EDITION]
            footnote.save()
            LogEntry.objects.log_action(
                # can't get user in a signal handler, so associate with script
                user_id=User.objects.get(username=settings.SCRIPT_USERNAME).id,
                content_type_id=ContentType.objects.get_for_model(Footnote).pk,
                object_id=footnote.pk,
                object_repr=str(footnote),
                action_flag=ADDITION,
            )

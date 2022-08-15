from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source


def get_or_create_footnote(instance, **kwargs):
    """On Annotation save, create digital edition Footnote if necessary"""
    # get pgpid from annotation content and match it to a Document
    document = Document.from_manifest_uri(
        instance.content["target"]["source"]["partOf"]["id"]
    )

    try:
        # try to get a DIGITAL_EDITION footnote for this source and document
        document.footnotes.get(
            source=Source.from_uri(instance.content["dc:source"]),
            doc_relation__contains=Footnote.DIGITAL_EDITION,
        )
    except Footnote.DoesNotExist:
        # create the DIGITAL_EDITION footnote
        footnote = document.footnotes.create(
            source=Source.from_uri(instance.content["dc:source"]),
            doc_relation=[Footnote.DIGITAL_EDITION],
        )
        LogEntry.objects.log_action(
            # can't get user in a signal handler, so associate with script
            user_id=User.objects.get(username=settings.SCRIPT_USERNAME).id,
            content_type_id=ContentType.objects.get_for_model(Footnote).pk,
            object_id=footnote.pk,
            object_repr=str(footnote),
            action_flag=ADDITION,
        )

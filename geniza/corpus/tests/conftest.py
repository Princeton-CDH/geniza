from datetime import datetime

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import get_current_timezone, make_aware
from taggit.models import Tag

from geniza.corpus.models import Document, DocumentType, Fragment, TextBlock


@pytest.fixture
def fragment(db):
    """A real fragment from CUL, with URLs for testing."""
    return Fragment.objects.create(
        shelfmark="CUL Add.2586",
        url="https://cudl.lib.cam.ac.uk/view/MS-ADD-02586",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586",
    )


@pytest.fixture
def multifragment(db):
    """A real multifragment object, with fake URLs for testing."""
    return Fragment.objects.create(
        shelfmark="T-S 16.377",
        url="https://example.com/view/TS16.377",
        iiif_url="https://iiif.example.com/TS16.377",
        is_multifragment=True,
    )


@pytest.fixture
def document(db, fragment):
    """A real legal document from the PGP."""
    doc = Document.objects.create(
        id=3951,
        description="""Deed of sale in which a father sells to his son a quarter
         of the apartment belonging to him in a house in the al- Mu'tamid
         passage of the Tujib quarter for seventeen dinars. Dated 1233.
         (Information from Mediterranean Society, IV, p. 281)""",
        doctype=DocumentType.objects.get_or_create(name="Legal")[0],
    )
    TextBlock.objects.create(document=doc, fragment=fragment)
    doc.tags.add("bill of sale", "real estate")
    dctype = ContentType.objects.get_for_model(Document)
    script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
    team_user = User.objects.get(username=settings.TEAM_USERNAME)
    LogEntry.objects.create(
        user=team_user,
        object_id=str(doc.pk),
        object_repr=str(doc)[:200],
        content_type=dctype,
        change_message="Initial data entry (spreadsheet), dated 2004",
        action_flag=ADDITION,
        action_time=make_aware(
            datetime(year=2004, month=1, day=1), timezone=get_current_timezone()
        ),
    )
    LogEntry.objects.create(
        user=script_user,
        object_id=str(doc.pk),
        object_repr=str(doc)[:200],
        content_type=dctype,
        change_message="Imported via script",
        action_flag=ADDITION,
        action_time=make_aware(
            datetime(year=2021, month=5, day=3), timezone=get_current_timezone()
        ),
    )
    return doc


@pytest.fixture
def join(db, fragment, multifragment):
    """A fake letter document that occurs on two different fragments."""
    doc = Document.objects.create(
        description="testing description",
        doctype=DocumentType.objects.get_or_create(name="Letter")[0],
    )
    TextBlock.objects.create(document=doc, fragment=fragment, order=1)
    TextBlock.objects.create(document=doc, fragment=multifragment, order=2)
    return doc

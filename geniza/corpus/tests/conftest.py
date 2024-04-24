from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import get_current_timezone, make_aware

from geniza.corpus.models import Document, DocumentType, Fragment, Manifest, TextBlock
from geniza.footnotes.models import Footnote

MockImporter = Mock()
# as of djiffy 0.7.2, import paths returns a list of objects
MockImporter.return_value.import_paths.return_value = []


@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
def make_fragment(manifest=True):
    """A real fragment from CUL, with URLs for testing."""
    return Fragment.objects.create(
        shelfmark="CUL Add.2586",
        old_shelfmarks="ULC Add. 2586",
        url="https://cudl.lib.cam.ac.uk/view/MS-ADD-02586",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586",
        manifest=Manifest.objects.create(
            uri="https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586", short_id="m"
        )
        if manifest
        else None,
    )


@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
def make_multifragment(manifest=True):
    """A real multifragment object, with fake URLs for testing."""
    return Fragment.objects.create(
        shelfmark="T-S 16.377",
        url="https://example.com/view/TS16.377",
        iiif_url="https://iiif.example.com/TS16.377",
        is_multifragment=True,
        manifest=Manifest.objects.create(
            uri="https://iiif.example.com/TS16.377", short_id="m2"
        )
        if manifest
        else None,
    )


def make_document(fragment):
    """A real legal document from the PGP."""
    doc = Document.objects.create(
        id=3951,
        description_en="""Deed of sale in which a father sells to his son a quarter
         of the apartment belonging to him in a house in the al- Mu'tamid
         passage of the Tujib quarter for seventeen dinars. Dated 1233.
         (Information from Mediterranean Society, IV, p. 281)""",
        doctype=DocumentType.objects.get_or_create(name_en="Legal")[0],
    )
    doc.tags.add("bill of sale", "real estate")
    TextBlock.objects.create(document=doc, fragment=fragment)
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


def make_join(fragment, multifragment):
    """A fake letter document that occurs on two different fragments."""
    doc = Document.objects.create(
        description_en="testing description",
        doctype=DocumentType.objects.get_or_create(name_en="Letter")[0],
    )
    TextBlock.objects.create(document=doc, fragment=fragment, order=1)
    TextBlock.objects.create(document=doc, fragment=multifragment, order=2)
    return doc


@pytest.fixture
def fragment(db):
    return make_fragment()


@pytest.fixture
def multifragment(db):
    return make_multifragment()


@pytest.fixture
def fragment_no_manifest(db):
    return make_fragment(manifest=False)


@pytest.fixture
def multifragment_no_manifest(db):
    return make_multifragment(manifest=False)


@pytest.fixture
def document(db, fragment):
    return make_document(fragment)


@pytest.fixture
def join(db, fragment, multifragment):
    return make_join(fragment, multifragment)


@pytest.fixture
def footnote(db, source, document):
    return Footnote.objects.create(
        source=source,
        content_object=document,
        location="p.1",
        doc_relation=Footnote.EDITION,
    )

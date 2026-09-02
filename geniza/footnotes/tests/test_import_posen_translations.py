import csv
import io
from unittest.mock import mock_open, patch

import pytest
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.corpus.models import Document, DocumentType
from geniza.footnotes.models import (
    Creator,
    Footnote,
    Source,
    SourceLanguage,
    SourceType,
)

# full set of column headers is irrelevant (the command indexes by position),
# but the row must be wide enough to reach the Posen URL column (index 11)
ROW_WIDTH = 13


def make_row(
    pgpid="",
    reassign="",
    title="A Test Chapter",
    footnote_id="",
    creator_ids="",
    posen_url="https://www.posenlibrary.com/node/1",
    pgp_url="",
):
    """Build a CSV row (list of cells) positioned to match spreadsheet columns."""
    row = [""] * ROW_WIDTH
    row[1] = str(pgpid)  # B pgpid
    row[4] = pgp_url  # E pgp_url
    row[6] = title  # G title
    row[7] = reassign  # H yes/no
    row[8] = str(footnote_id)  # I existing footnote id
    row[10] = creator_ids  # K creator pks
    row[11] = posen_url  # L stable Posen url
    return row


def csv_text(rows):
    """Serialize a header row plus data rows to CSV text (with proper quoting)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["col%d" % i for i in range(ROW_WIDTH)])
    writer.writerows(rows)
    return buf.getvalue()


def run_command(rows, *args):
    """Invoke the command with an in-memory CSV of the given rows."""
    with patch(
        "geniza.footnotes.management.commands.import_posen_translations.open",
        mock_open(read_data=csv_text(rows)),
    ):
        call_command("import_posen_translations", "posen.csv", *args)


def make_document():
    """Create a minimal document to attach footnotes to."""
    return Document.objects.create(
        doctype=DocumentType.objects.get_or_create(name_en="Legal")[0]
    )


@pytest.mark.django_db
def test_creates_source_and_translation_footnote():
    doc = make_document()
    ashur = Creator.objects.create(first_name_en="Amir", last_name_en="Ashur")
    outhwaite = Creator.objects.create(first_name_en="Ben", last_name_en="Outhwaite")

    run_command(
        [
            make_row(
                pgpid=doc.pk,
                reassign="no",
                title="Posen Source",
                creator_ids="%d; %d" % (ashur.pk, outhwaite.pk),
                posen_url="https://www.posenlibrary.com/node/13542",
            )
        ]
    )

    # a new Book Section source with the shared Posen field values
    source = Source.objects.get(title="Posen Source")
    assert source.source_type.type == "Book Section"
    assert source.year == 2026
    assert source.publisher == "Yale University Press"
    assert source.place_published == "New Haven, Connecticut and London"
    assert source.journal == "Posen Library of Jewish Culture and Civilization"
    assert source.volume == "3"
    assert source.url == "https://www.posenlibrary.com/node/13542"
    assert list(source.languages.values_list("name", flat=True)) == ["English"]
    assert source.slug  # slug generated from authors/title/year
    # authors preserved in spreadsheet order
    assert [
        (a.sort_order, a.creator_id)
        for a in source.authorship_set.order_by("sort_order")
    ] == [(1, ashur.pk), (2, outhwaite.pk)]

    # a content-less Translation footnote linking the source to the document
    footnote = Footnote.objects.get(source=source)
    assert footnote.get_doc_relation_display() == "Translation"
    assert footnote.content is None
    assert footnote.object_id == doc.pk
    assert footnote.content_type == ContentType.objects.get_for_model(Document)

    # both creations are logged as additions under the script user
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 2


@pytest.mark.django_db
def test_leaves_other_footnotes_untouched():
    # translations already attached to a separate source must not be reassigned
    doc = make_document()
    creator = Creator.objects.create(first_name_en="Geoffrey", last_name_en="Khan")
    other_source = Source.objects.create(
        title="Other Source",
        source_type=SourceType.objects.get(type="Book"),
    )
    existing = Footnote.objects.create(
        source=other_source,
        content_object=doc,
        doc_relation=[Footnote.EDITION],
    )

    run_command([make_row(pgpid=doc.pk, reassign="no", creator_ids=str(creator.pk))])

    existing.refresh_from_db()
    assert existing.source_id == other_source.pk  # unchanged


@pytest.mark.django_db
def test_reassigns_existing_footnote():
    doc = make_document()
    creator = Creator.objects.create(first_name_en="Arnold", last_name_en="Franklin")
    old_source = Source.objects.create(
        title="Wrong Source",
        source_type=SourceType.objects.get(type="Book"),
    )
    footnote = Footnote.objects.create(
        source=old_source,
        content_object=doc,
        doc_relation=[Footnote.DIGITAL_TRANSLATION],
        content={"body": "translation content"},
    )

    run_command(
        [
            make_row(
                reassign="yes",
                title="Test Source",
                footnote_id=footnote.pk,
                creator_ids=str(creator.pk),
            )
        ]
    )

    new_source = Source.objects.get(title="Test Source")
    footnote.refresh_from_db()
    # reassigned to the new source, but content and relation preserved
    assert footnote.source_id == new_source.pk
    assert footnote.content == {"body": "translation content"}
    assert footnote.get_doc_relation_display() == "Digital Translation"
    # no new footnote created; old source is left in place
    assert Footnote.objects.count() == 1
    assert Source.objects.filter(pk=old_source.pk).exists()
    # reassignment logged as a change
    assert (
        LogEntry.objects.filter(action_flag=CHANGE, object_id=footnote.pk).count() == 1
    )


@pytest.mark.django_db
def test_idempotent_reruns():
    doc = make_document()
    creator = Creator.objects.create(first_name_en="Amir", last_name_en="Ashur")
    rows = [
        make_row(
            pgpid=doc.pk,
            reassign="no",
            title="Posen Source",
            creator_ids=str(creator.pk),
        )
    ]

    # running twice should not result in duplicates
    run_command(rows)
    run_command(rows)
    assert Source.objects.filter(title="Posen Source").count() == 1
    assert Footnote.objects.count() == 1


@pytest.mark.django_db
def test_dryrun_makes_no_changes():
    doc = make_document()
    creator = Creator.objects.create(first_name_en="Amir", last_name_en="Ashur")

    run_command(
        [make_row(pgpid=doc.pk, reassign="no", creator_ids=str(creator.pk))],
        "--dryrun",
    )

    assert not Source.objects.filter(journal__startswith="Posen").exists()
    assert Footnote.objects.count() == 0
    assert LogEntry.objects.count() == 0


@pytest.mark.django_db
def test_skips_bad_rows_and_reports():
    doc = make_document()
    creator = Creator.objects.create(first_name_en="Amir", last_name_en="Ashur")
    cid = str(creator.pk)
    missing_creator_id = str(creator.pk + 1000)

    rows = [
        # "no" row with multiple PGPIDs = ambiguous, skip
        make_row(pgpid="19297, 19296", reassign="no", creator_ids=cid),
        # "no" row with a non-numeric PGPID
        make_row(pgpid="not in PGP", reassign="no", creator_ids=cid),
        # "no" row whose document does not exist
        make_row(pgpid="99999999", reassign="no", creator_ids=cid),
        # "yes" row missing the footnote id
        make_row(reassign="yes", footnote_id="", creator_ids=cid),
        # "yes" row referencing a nonexistent footnote
        make_row(reassign="yes", footnote_id="99999999", creator_ids=cid),
        # unknown Column H value
        make_row(pgpid=doc.pk, reassign="bad", creator_ids=cid),
        # unknown creator id
        make_row(pgpid=doc.pk, reassign="no", creator_ids=missing_creator_id),
        # non-numeric creator id
        make_row(pgpid=doc.pk, reassign="no", creator_ids="abc"),
        # no creator id at all
        make_row(pgpid=doc.pk, reassign="no", creator_ids=""),
        # valid document and creator, but no title
        make_row(pgpid=doc.pk, reassign="no", title="", creator_ids=cid),
        # fully blank row is silently ignored (not counted as a skip)
        [""] * ROW_WIDTH,
    ]
    run_command(rows)

    # every row was skipped; nothing created
    assert Source.objects.count() == 0
    assert Footnote.objects.count() == 0


@pytest.mark.django_db
def test_creator_ids_tolerate_blank_parts():
    # separators with empty segments (e.g. a trailing ";") are ignored
    doc = make_document()
    ashur = Creator.objects.create(first_name_en="Amir", last_name_en="Ashur")
    outhwaite = Creator.objects.create(first_name_en="Ben", last_name_en="Outhwaite")

    run_command(
        [
            make_row(
                pgpid=doc.pk,
                reassign="no",
                creator_ids="%d; ; %d;" % (ashur.pk, outhwaite.pk),
            )
        ]
    )

    source = Source.objects.get()
    assert list(
        source.authorship_set.order_by("sort_order").values_list(
            "creator_id", flat=True
        )
    ) == [ashur.pk, outhwaite.pk]


@pytest.mark.django_db
def test_reassign_non_digital_translation_and_rerun():
    # a footnote that is not a Digital Translation is still reassigned (with a
    # warning), and reassigning again is a no-op
    doc = make_document()
    creator = Creator.objects.create(first_name_en="Amir", last_name_en="Ashur")
    old_source = Source.objects.create(
        title="Wrong Source", source_type=SourceType.objects.get(type="Book")
    )
    footnote = Footnote.objects.create(
        source=old_source,
        content_object=doc,
        doc_relation=[Footnote.EDITION],
    )
    rows = [
        make_row(reassign="yes", footnote_id=footnote.pk, creator_ids=str(creator.pk))
    ]

    run_command(rows)
    footnote.refresh_from_db()
    new_source = Source.objects.get(title="A Test Chapter")
    assert footnote.source_id == new_source.pk

    # second run: footnote is already on the new source, so nothing changes
    run_command(rows)
    assert (
        LogEntry.objects.filter(action_flag=CHANGE, object_id=footnote.pk).count() == 1
    )


@pytest.mark.django_db
def test_skip_indexing_disconnects_signal_handler():
    doc = make_document()
    creator = Creator.objects.create(first_name_en="Amir", last_name_en="Ashur")

    with patch(
        "geniza.footnotes.management.commands.import_posen_translations."
        "IndexableSignalHandler.disconnect"
    ) as mock_disconnect:
        run_command(
            [make_row(pgpid=doc.pk, reassign="no", creator_ids=str(creator.pk))],
            "--skip-indexing",
        )
    mock_disconnect.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize(
    # the command checks these records in order and raises on the first missing
    # one, so each must be deleted in its own run to cover all three branches
    "records",
    [
        User.objects.filter(username=settings.SCRIPT_USERNAME),
        SourceType.objects.filter(type="Book Section"),
        SourceLanguage.objects.filter(name="English"),
    ],
    ids=["script_user", "book_section", "english"],
)
def test_errors_when_required_records_missing(records):
    # command should raise error if required records are missing
    records.delete()
    with pytest.raises(CommandError):
        run_command([make_row(pgpid=1, reassign="no", creator_ids="1")])


@pytest.mark.django_db
def test_file_not_found():
    with pytest.raises(CommandError):
        call_command("import_posen_translations", "nonexistent.csv")

import os
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.corpus.management.commands import merge_documents
from geniza.corpus.models import Document, TextBlock


@pytest.mark.django_db
@patch.object(Document, "merge_with")
def test_merge_group_error_handling(mock_merge_with, document, join):
    stderr = StringIO()
    # no primary
    command = merge_documents.Command(stderr=stderr)
    rval = command.merge_group("a", [])
    assert "Could not identify primary document" in stderr.getvalue()
    assert rval == 0
    # no merge docs
    command.merge_group("a", [{"pgpid": "1", "role": "primary"}])
    assert "No merge documents" in stderr.getvalue()

    # primary does not exist in the database
    command.merge_group(
        "a",
        [
            {"pgpid": 14151, "role": "primary", "status": "test merge"},
            {"pgpid": 23426, "role": ""},
        ],
    )
    assert "Primary document 14151 not found" in stderr.getvalue()

    # not all merge documents exist in the database
    command.merge_group(
        "a",
        [
            {"pgpid": document.id, "role": "primary", "status": "test merge"},
            {"pgpid": 23043, "role": ""},
            {"pgpid": join.id, "role": ""},
        ],
    )
    assert "Not all merge documents found" in stderr.getvalue()


@pytest.mark.django_db
@patch.object(Document, "merge_with")
def test_merge_group(mock_merge_with, document, join):
    stderr = StringIO()
    command = merge_documents.Command(stderr=stderr)
    rval = command.merge_group(
        "a",
        [
            {"pgpid": document.id, "role": "primary", "status": "test merge"},
            {"pgpid": join.id, "role": ""},
        ],
    )
    assert rval == 1

    # inspect the call (can't use assert because document eqaulity check fails)
    args, kwargs = mock_merge_with.call_args
    assert args[0][0].pk == join.pk
    assert args[1] == "test merge"


@pytest.mark.django_db
def test_handle_file_not_found(tmpdir):
    command = merge_documents.Command()
    with pytest.raises(CommandError) as err:
        command.handle(mode="merge", path="/tmp/example/not-here.csv")
    assert "Report file not found: /tmp/example/not-here.csv" in str(err)

    # test with default path
    # change working directory to tmpdir to ensure file is not found
    os.chdir(tmpdir)
    stderr = StringIO()
    with pytest.raises(CommandError) as err:
        call_command("merge_documents", "merge", stderr=stderr)

    assert "Report file not found: merge-report.csv" in str(err)


@patch.object(merge_documents.Command, "get_merge_candidates")
@patch.object(merge_documents.Command, "group_merge_candidates")
@patch.object(merge_documents.Command, "generate_report")
def test_handle_report(mock_generate_report, mock_group_merge, mock_get_merge):
    cmd = merge_documents.Command()
    cmd.handle(mode="report", path="test-report.csv")
    # confirm that the correct sequence of methods is called
    mock_get_merge.assert_any_call()
    mock_group_merge.assert_called_with(mock_get_merge.return_value)
    mock_generate_report.assert_called_with(
        mock_group_merge.return_value, "test-report.csv"
    )


@patch.object(merge_documents.Command, "merge_group")
@patch.object(merge_documents.Command, "load_report")
def test_handle_merge(mock_load_report, mock_merge_group):
    stdout = StringIO()
    path = "merge-groups.csv"
    cmd = merge_documents.Command(stdout=stdout)
    # return some mock groups from load method
    mock_load_report.return_value = [
        # group id, group
        ("a", [1, 2, 3]),
        ("b", [4, 5, 5]),
    ]
    # report success, then failure from merge method
    mock_merge_group.side_effect = (1, 0)
    cmd.handle(mode="merge", path=path)
    # confirm that the correct sequence of methods is called
    mock_load_report.assert_called_with(path)
    for group_id, docs in mock_load_report.return_value:
        mock_merge_group.assert_any_call(group_id, docs)
    output = stdout.getvalue()
    assert "Successfully merged 1 group" in output
    assert "skipped 1" in output


@pytest.mark.django_db
def test_get_merge_candidates(fragment, multifragment, join):
    # looks for more than one document on the same set of fragments
    # join is a document associated with fragment & multifragment
    # create two other documents to be merged
    doc2 = Document.objects.create(
        description="see other fragment", doctype=join.doctype
    )
    # associate in same order as join
    TextBlock.objects.create(document=doc2, fragment=fragment, order=1)
    TextBlock.objects.create(document=doc2, fragment=multifragment, order=2)

    doc3 = Document.objects.create(
        description="see other fragment", doctype=join.doctype
    )
    # associate in different order as join doc
    TextBlock.objects.create(document=doc3, fragment=fragment, order=2)
    TextBlock.objects.create(document=doc3, fragment=multifragment, order=1)

    # doc on the same fragments with different type (unknown)
    unknown_doc = Document.objects.create(
        description="something else",
    )
    # associate in same order as join doc
    TextBlock.objects.create(document=unknown_doc, fragment=fragment, order=1)
    TextBlock.objects.create(document=unknown_doc, fragment=multifragment, order=3)

    command = merge_documents.Command()
    candidates = command.get_merge_candidates()

    # should result in one candidate group
    assert len(candidates) == 1
    # key should be shelfmark + type
    shelfmark_type = "%s / %s" % (join.shelfmark, join.doctype.name)
    assert shelfmark_type in candidates
    # should not include document with different type
    assert len(candidates[shelfmark_type]) == 3
    for doc in [join, doc2, doc3]:
        assert doc in candidates[shelfmark_type]


@pytest.mark.django_db
def test_group_merge_candidates_same_desc():
    # merge based on same description
    command = merge_documents.Command()
    doc1 = Document.objects.create(description="a marriage contract")
    doc2 = Document.objects.create(description=doc1.description)
    shelfmark_id = "shelfmark / letter"
    report_rows = command.group_merge_candidates(
        {
            shelfmark_id: [doc1, doc2],
        }
    )
    assert report_rows[0] == [
        shelfmark_id,
        1,
        "MERGE",
        "all descriptions match",
        "primary",
        doc1.pk,
        doc1.description,
    ]
    assert report_rows[1] == [
        shelfmark_id,
        1,
        "MERGE",
        "all descriptions match",
        "merge",
        doc2.pk,
        doc2.description,
    ]


@pytest.mark.django_db
def test_group_merge_candidates_empty_description():
    # merge based on empty description text in secondary documents
    command = merge_documents.Command()
    doc1 = Document.objects.create(description="a marriage contract")
    doc2 = Document.objects.create()
    shelfmark_id = "shelfmark / letter"
    report_rows = command.group_merge_candidates(
        {
            shelfmark_id: [doc1, doc2],
        }
    )
    # status should be merge; rationale from empty description
    assert report_rows[0][2] == "MERGE"
    assert report_rows[0][3] == "one description, others empty"


@pytest.mark.django_db
def test_group_merge_candidates_see_join():
    # merge based on "see join" text in secondary documents
    command = merge_documents.Command()
    doc1 = Document.objects.create(description="a marriage contract")
    doc2 = Document.objects.create(description="See join.")
    shelfmark_id = "shelfmark / letter"
    report_rows = command.group_merge_candidates(
        {
            shelfmark_id: [doc1, doc2],
        }
    )
    # status should be merge; rationale should be "see join"
    assert report_rows[0][2] == "MERGE"
    assert report_rows[0][3] == "see join"
    assert report_rows[0][4] == "primary"
    assert report_rows[0][5] == doc1.pk


@pytest.mark.django_db
def test_group_merge_candidates_see_pgpid():
    # merge based on "see pgpid" text in secondary documents
    command = merge_documents.Command()
    doc1 = Document.objects.create(description="a marriage contract", pk=134552)
    doc2 = Document.objects.create(description="See PGPID %d" % doc1.pk)
    shelfmark_id = "shelfmark / unknown"
    report_rows = command.group_merge_candidates(
        {
            shelfmark_id: [doc1, doc2],
        }
    )
    # status should be merge; rationale should be "see join"
    assert report_rows[0][2] == "MERGE"
    assert report_rows[0][3] == "see PGPID"


@pytest.mark.django_db
def test_generate_report(tmpdir):
    report_path = tmpdir.join("report.csv")
    command = merge_documents.Command()
    test_rows = [["a", "b", "c", "d", "e", "f"], ["g", "h", "j", "k", "l", "m"]]
    command.generate_report(test_rows, report_path)
    report = report_path.read()
    assert "merge group,group id,action,status,role,pgpid,description" in report
    for row in test_rows:
        assert ",".join(row) in report

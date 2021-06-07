import os
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.corpus.management.commands import merge_joins
from geniza.corpus.models import Document


@pytest.mark.django_db
@patch.object(Document, "merge_with")
def test_merge_group_error_handling(mock_merge_with, document, join):
    stderr = StringIO()
    # no primary
    command = merge_joins.Command(stderr=stderr)
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
    command = merge_joins.Command(stderr=stderr)
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
    command = merge_joins.Command()
    with pytest.raises(CommandError) as err:
        command.handle(mode="merge", path="/tmp/example/not-here.csv")
    assert "Report file not found: /tmp/example/not-here.csv" in str(err)

    # test with default path
    # change working directory to tmpdir to ensure file is not found
    os.chdir(tmpdir)
    stderr = StringIO()
    with pytest.raises(CommandError) as err:
        call_command("merge_joins", "merge", stderr=stderr)

    assert "Report file not found: merge-report.csv" in str(err)

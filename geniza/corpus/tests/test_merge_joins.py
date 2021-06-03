from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management.base import CommandError

from geniza.corpus.management.commands import merge_joins
from geniza.corpus.models import Document


@pytest.mark.django_db
@patch.object(Document, "merge_with")
def test_merge_group_error_handling(document, join):
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

from collections import defaultdict
from unittest.mock import mock_open, patch

import pytest
from attrdict import AttrMap
from django.contrib.admin.models import CHANGE, LogEntry
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.corpus.management.commands import add_links
from geniza.corpus.models import Fragment


@pytest.mark.django_db
def test_handle():
    command = add_links.Command()
    command.csv_path = "foo.csv"
    csv_data = "\n".join(
        [
            "linkID,object_id,link_type,link_title,link_target,link_attribution",
            "7179,451,goitein_note,Goitein Note,5C.1.1 NN_ Michael_ pt.1/AIU VII.E.5_1 (PGPID 451).pdf",
        ]
    )
    mockfile = mock_open(read_data=csv_data)

    with patch("geniza.corpus.management.commands.add_links.open", mockfile):
        command.handle()


@pytest.mark.django_db
def test_call_command():
    # test calling from command line; file not found on nonexistent csv
    with pytest.raises(CommandError):
        call_command("add_links", "nonexistent.csv")


@pytest.mark.django_db
def test_handle_missing_csv_headers():
    command = add_links.Command()
    # none of the headers match
    csv_data = "\n".join(["foo,bar,baz", "one,two,three"])
    mockfile = mock_open(read_data=csv_data)

    with patch("geniza.corpus.management.commands.add_links.open", mockfile):
        with pytest.raises(CommandError) as err:
            command.handle()
        assert "CSV must include" in str(err)


@pytest.mark.django_db
def test_handle_file_not_found():
    command = add_links.Command()
    with pytest.raises(CommandError) as err:
        command.handle(csv="/tmp/example/not-here.csv")
    assert "CSV file not found" in str(err)


@pytest.mark.django_db
def test_add_link():
    pass

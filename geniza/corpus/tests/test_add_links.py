from collections import Counter
from io import StringIO
from unittest.mock import Mock, mock_open, patch

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.corpus.management.commands import add_links
from geniza.corpus.models import Fragment
from geniza.footnotes.models import Source, SourceType


@pytest.fixture
def jewish_traders(db):
    book_type = SourceType.objects.get(type="Book")
    # not the full record; just what is needed for testing this script
    return Source.objects.create(
        title="Letters of Medieval Jewish Traders", source_type=book_type
    )


@pytest.fixture
def india_book(db):
    book_type = SourceType.objects.get(type="Book")
    # not alll records; just enough to test this script
    return Source.objects.bulk_create(
        [
            Source(title="India Book 1", source_type=book_type),
            Source(title="India Book 2", source_type=book_type),
        ]
    )


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.add_links.Command.setup", Mock())
class TestAddLinksSkipSetup:
    # all of these tests skip the command that requests authors and sources from the db

    @patch("geniza.corpus.management.commands.add_links.Command.add_link")
    def test_handle(self, mock_add_link):
        stdout = StringIO()
        command = add_links.Command(stdout=stdout)
        command.csv_path = "foo.csv"
        csv_data = "\n".join(
            [
                "object_id,link_type,link_target",
                "451,goitein_note,link_to_doc.pdf",
            ]
        )
        mockfile = mock_open(read_data=csv_data)

        # populate fields expected by summary
        command.stats = Counter()
        for stat in ["ignored", "errored", "document_not_found", "sources_created"]:
            command.stats[stat] = 0

        with patch("geniza.corpus.management.commands.add_links.open", mockfile):
            command.handle()
            mock_add_link.assert_called_with(
                {
                    "object_id": "451",
                    "link_type": "goitein_note",
                    "link_target": "link_to_doc.pdf",
                }
            )

        # check summary output
        output = stdout.getvalue()
        assert "Created 0 new sources" in output
        assert "Created 0 new footnotes" in output

    def test_call_command(self):
        # test calling from command line; file not found on nonexistent csv
        with pytest.raises(CommandError):
            call_command("add_links", "nonexistent.csv")

    def test_handle_missing_csv_headers(self):
        command = add_links.Command(stdout=StringIO())
        # none of the headers match
        csv_data = "\n".join(["foo,bar,baz", "one,two,three"])
        mockfile = mock_open(read_data=csv_data)

        with patch("geniza.corpus.management.commands.add_links.open", mockfile):
            with pytest.raises(CommandError) as err:
                command.handle()
            assert "CSV is missing required fields" in str(err)

    def test_handle_file_not_found(self):
        command = add_links.Command(stdout=StringIO())
        with pytest.raises(CommandError) as err:
            command.handle(csv="/tmp/example/not-here.csv")
        assert "CSV file not found" in str(err)

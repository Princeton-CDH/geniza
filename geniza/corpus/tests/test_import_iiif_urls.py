from unittest.mock import patch, mock_open
from attrdict import AttrMap
import pytest

from django.contrib.admin.models import CHANGE, LogEntry
from django.core.management.base import CommandError

from geniza.corpus.management.commands import import_iiif_urls
from geniza.corpus.models import Fragment


@pytest.mark.django_db
def test_handle():
    fragment = Fragment.objects.create(shelfmark="T-S NS 305.65")

    command = import_iiif_urls.Command()
    command.csv_path = "foo.csv"
    csv_data = "\n".join(
        [
            "shelfmark,url",
            "T-S NS 305.65,https://cudl.lib.cam.ac.uk/view/MS-TS-NS-00305-00065",
            "T-S NS 305.69,https://cudl.lib.cam.ac.uk/view/MS-TS-NS-00305-00069",
            "T-S NS 305.75,https://cudl.lib.cam.ac.uk/view/MS-TS-NS-00305-00075",
        ]
    )
    mockfile = mock_open(read_data=csv_data)

    with patch("geniza.corpus.management.commands.import_iiif_urls.open", mockfile):
        command.handle()

    fragment = Fragment.objects.get(shelfmark="T-S NS 305.65")
    assert fragment.iiif_url == "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-00305-00065"


@pytest.mark.django_db
def test_handle_missing_csv_headers():
    command = import_iiif_urls.Command()
    # none of the headers match
    csv_data = "\n".join(["foo,bar,baz", "one,two,three"])
    mockfile = mock_open(read_data=csv_data)

    with patch("geniza.corpus.management.commands.import_iiif_urls.open", mockfile):
        with pytest.raises(CommandError) as err:
            command.handle()
        assert "CSV must include 'shelfmark'" in str(err)

    # shelfmark but no url
    csv_data = "\n".join(["shelfmark,view", "a,b"])
    mockfile = mock_open(read_data=csv_data)

    with patch("geniza.corpus.management.commands.import_iiif_urls.open", mockfile):
        with pytest.raises(CommandError) as err:
            command.handle()
        assert "CSV must include 'shelfmark'" in str(err)

    # shelfmark and url — ok
    csv_data = "\n".join(["shelfmark,url", "a,b"])
    mockfile = mock_open(read_data=csv_data)
    with patch("geniza.corpus.management.commands.import_iiif_urls.open", mockfile):
        with patch.object(command, "add_fragment_urls"):
            # no exception
            command.handle()

    # shelfmark and iiif url — ok
    csv_data = "\n".join(["shelfmark,iiif_url", "a,b"])
    mockfile = mock_open(read_data=csv_data)
    with patch("geniza.corpus.management.commands.import_iiif_urls.open", mockfile):
        with patch.object(command, "add_fragment_urls"):
            # no exception
            command.handle()

    # all three
    csv_data = "\n".join(["shelfmark,url,iiif_url", "a,b"])
    mockfile = mock_open(read_data=csv_data)
    with patch("geniza.corpus.management.commands.import_iiif_urls.open", mockfile):
        with patch.object(command, "add_fragment_urls"):
            # no excetion
            command.handle()


@pytest.mark.django_db
def test_handle_file_not_found():
    command = import_iiif_urls.Command()
    with pytest.raises(CommandError) as err:
        command.handle(csv="/tmp/example/not-here.csv")
        assert "FileNotFound" in str(err)


@pytest.mark.django_db
def test_view_to_iiif_url():
    command = import_iiif_urls.Command()
    assert (
        command.view_to_iiif_url("https://cudl.lib.cam.ac.uk/view/MS-ADD-02586")
        == "https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586"
    )

    assert (
        command.view_to_iiif_url("https://cudl.lib.cam.ac.uk/view/MS-ADD-03430/1")
        == "https://cudl.lib.cam.ac.uk/iiif/MS-ADD-03430"
    )

    assert command.view_to_iiif_url("https://example.com/iiif/1234") == ""


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.import_iiif_urls.Command.log_change")
def test_add_fragment_urls(mock_log_change):
    # Ensure shelfmark not existing is properly handled.
    command = import_iiif_urls.Command()
    row = AttrMap({"shelfmark": "mm", "url": "example.com"})
    command.add_fragment_urls(row)  # Test would fail if error were raised
    assert command.stats["not_found"] == 1
    assert not mock_log_change.call_count

    # Ensure that the iiif url is not overwritten unless overwrite arg is provided
    command = import_iiif_urls.Command()
    command.overwrite = None
    command.dryrun = None
    orig_frag = Fragment.objects.create(
        shelfmark="T-S NS 305.66",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = AttrMap(
        {
            "shelfmark": orig_frag.shelfmark,
            "url": "https://cudl.lib.cam.ac.uk/view/MS-TS-NS-J-00600",
        }
    )
    command.add_fragment_urls(row)
    fragment = Fragment.objects.get(shelfmark=orig_frag.shelfmark)
    assert fragment.url == row["url"]
    assert fragment.iiif_url == orig_frag.iiif_url
    assert command.stats["url_added"] == 1
    assert not command.stats["iiif_added"]
    assert not command.stats["iiif_updated"]
    assert not command.stats["url_updated"]
    mock_log_change.assert_called_with(fragment, "added URL")

    command = import_iiif_urls.Command()
    command.overwrite = True
    command.dryrun = None
    orig_frag = Fragment.objects.create(
        shelfmark="T-S NS 305.75",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = AttrMap(
        {
            "shelfmark": orig_frag.shelfmark,
            "url": "https://cudl.lib.cam.ac.uk/view/MS-TS-NS-J-00600",
        }
    )
    command.add_fragment_urls(row)
    fragment = Fragment.objects.get(shelfmark=orig_frag.shelfmark)
    assert fragment.iiif_url != orig_frag.iiif_url
    assert fragment.iiif_url == "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00600"
    assert command.stats["iiif_updated"] == 1
    mock_log_change.assert_called_with(fragment, "added URL and updated IIIF URL")

    # Ensure that changes aren't saved if dryrun argument is provided
    mock_log_change.reset_mock()
    command = import_iiif_urls.Command()
    command.overwrite = None
    command.dryrun = True
    orig_frag = Fragment.objects.create(
        shelfmark="T-S NS 305.80",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = AttrMap(
        {
            "shelfmark": orig_frag.shelfmark,
            "url": "https://cudl.lib.cam.ac.uk/view/MS-TS-NS-J-00600",
        }
    )
    command.add_fragment_urls(row)
    fragment = Fragment.objects.get(shelfmark=orig_frag.shelfmark)
    assert fragment.iiif_url == orig_frag.iiif_url
    assert not mock_log_change.call_count


@pytest.mark.django_db
def test_log_change(fragment):
    command = import_iiif_urls.Command()
    command.log_change(fragment, "added url")
    log_entry = LogEntry.objects.get(object_id=fragment.pk)
    assert log_entry.action_flag == CHANGE
    assert log_entry.change_message == "added url"

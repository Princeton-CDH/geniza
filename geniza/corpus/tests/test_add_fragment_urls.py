from collections import defaultdict
from io import StringIO
from unittest.mock import Mock, mock_open, patch

import pytest
from addict import Dict
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.corpus.management.commands import add_fragment_urls
from geniza.corpus.models import Collection, Fragment

MockImporter = Mock()
# as of djiffy 0.7.2, import paths returns a list of objects
MockImporter.return_value.import_paths.return_value = []


@pytest.mark.django_db
@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
def test_handle():
    fragment = Fragment.objects.create(shelfmark="T-S NS 305.65")

    command = add_fragment_urls.Command()
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

    with patch("geniza.corpus.management.commands.add_fragment_urls.open", mockfile):
        command.handle()

    fragment = Fragment.objects.get(shelfmark="T-S NS 305.65")
    assert fragment.iiif_url == "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-00305-00065"


@pytest.mark.django_db
def test_call_command():
    # test calling from command line; file not found on nonexistent csv
    with pytest.raises(CommandError):
        call_command("add_fragment_urls", "nonexistent.csv")


@pytest.mark.django_db
def test_handle_missing_csv_headers():
    command = add_fragment_urls.Command()
    # none of the headers match
    csv_data = "\n".join(["foo,bar,baz", "one,two,three"])
    mockfile = mock_open(read_data=csv_data)

    with patch("geniza.corpus.management.commands.add_fragment_urls.open", mockfile):
        with pytest.raises(CommandError) as err:
            command.handle()
        assert "CSV must include 'shelfmark'" in str(err)

    # shelfmark but no url
    csv_data = "\n".join(["shelfmark,view", "a,b"])
    mockfile = mock_open(read_data=csv_data)

    with patch("geniza.corpus.management.commands.add_fragment_urls.open", mockfile):
        with pytest.raises(CommandError) as err:
            command.handle()
        assert "CSV must include 'shelfmark'" in str(err)

    # shelfmark and url — ok
    csv_data = "\n".join(["shelfmark,url", "a,b"])
    mockfile = mock_open(read_data=csv_data)
    with patch("geniza.corpus.management.commands.add_fragment_urls.open", mockfile):
        with patch.object(command, "add_fragment_urls"):
            # no exception
            command.handle()

    # shelfmark and iiif url — ok
    csv_data = "\n".join(["shelfmark,iiif_url", "a,b"])
    mockfile = mock_open(read_data=csv_data)
    with patch("geniza.corpus.management.commands.add_fragment_urls.open", mockfile):
        with patch.object(command, "add_fragment_urls"):
            # no exception
            command.handle()

    # all three
    csv_data = "\n".join(["shelfmark,url,iiif_url", "a,b"])
    mockfile = mock_open(read_data=csv_data)
    with patch("geniza.corpus.management.commands.add_fragment_urls.open", mockfile):
        with patch.object(command, "add_fragment_urls"):
            # no excetion
            command.handle()


@pytest.mark.django_db
def test_handle_file_not_found():
    command = add_fragment_urls.Command()
    with pytest.raises(CommandError) as err:
        command.handle(csv="/tmp/example/not-here.csv")
    assert "CSV file not found" in str(err)


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.add_fragment_urls.Command.log_change")
@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
def test_add_fragment_urls(mock_log_change):
    # Ensure shelfmark not existing is properly handled.
    command = add_fragment_urls.Command()
    row = Dict({"shelfmark": "mm", "url": "example.com"})
    command.add_fragment_urls(row)  # Test would fail if error were raised
    assert command.stats["not_found"] == 1
    assert not mock_log_change.call_count

    # Ensure that the iiif url is not overwritten unless overwrite arg is provided
    command = add_fragment_urls.Command()
    command.overwrite = None
    command.dryrun = None
    orig_frag = Fragment.objects.create(
        shelfmark="T-S NS 305.66",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = Dict(
        {
            "shelfmark": orig_frag.shelfmark,
            "url": "https://cudl.lib.cam.ac.uk/view/MS-TS-NS-J-00600",
            "material_support": "Paper",
            "provenance": "Geniza",
        }
    )
    command.add_fragment_urls(row)
    fragment = Fragment.objects.get(shelfmark=orig_frag.shelfmark)
    assert fragment.url == row["url"]
    assert fragment.iiif_url == orig_frag.iiif_url
    assert fragment.material_support.name == row["material_support"]
    assert fragment.provenance_display.name == row["provenance"]
    assert command.stats["url_added"] == 1
    assert not command.stats["iiif_added"]
    assert not command.stats["iiif_updated"]
    assert not command.stats["url_updated"]
    mock_log_change.assert_called_with(fragment, "added URL")

    command = add_fragment_urls.Command()
    command.overwrite = True
    command.dryrun = None
    orig_frag = Fragment.objects.create(
        shelfmark="T-S NS 305.75",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = Dict(
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

    # test updating url — url matches, should skip
    fragment.url = row.url
    fragment.save()
    command.stats = defaultdict(int)
    command.add_fragment_urls(row)
    assert not command.stats["url_updated"]
    assert not command.stats["url_added"]
    assert command.stats["skipped"] == 1

    # fragment url is set but does not match, no overwrite
    fragment.url = "http://example.com/fragment/view"
    fragment.save()
    command.overwrite = False
    command.stats = defaultdict(int)
    command.add_fragment_urls(row)
    assert not command.stats["url_updated"]
    assert not command.stats["url_added"]
    assert command.stats["skipped"] == 1

    # url mismatch, overwrite specified
    command.overwrite = True
    command.stats = defaultdict(int)
    command.add_fragment_urls(row)
    assert command.stats["url_updated"] == 1
    assert not command.stats["url_added"]
    assert not command.stats["skipped"]

    # Ensure that changes aren't saved if dryrun argument is provided
    mock_log_change.reset_mock()
    command = add_fragment_urls.Command()
    command.overwrite = None
    command.dryrun = True
    orig_frag = Fragment.objects.create(
        shelfmark="T-S NS 305.80",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = Dict(
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
    command = add_fragment_urls.Command()
    command.log_change(fragment, "added url")
    log_entry = LogEntry.objects.get(object_id=fragment.pk)
    assert log_entry.action_flag == CHANGE
    assert log_entry.change_message == "added url"


@pytest.mark.django_db
def test_handle_collection_option():
    command = add_fragment_urls.Command()
    # collection requires create
    with pytest.raises(CommandError) as err:
        command.handle(csv="foo.csv", collection=1)
    assert "--collection can only be used with --create" in str(err)

    # collection must exist
    with pytest.raises(CommandError) as err:
        command.handle(csv="foo.csv", create=True, collection=12345)
    assert "Collection not found: 12345" in str(err)

    # valid collection is used for new fragments
    collection = Collection.objects.create(library="Katz Center", lib_abbrev="CAJS")
    mockfile = mock_open(
        read_data="shelfmark,iiif_url\nCAJS RAR MS 1,https://example.com/iiif/1/manifest"
    )
    with patch("geniza.corpus.management.commands.add_fragment_urls.open", mockfile):
        with patch.object(command, "create_fragment") as mock_create:
            command.handle(csv="foo.csv", create=True, collection=collection.pk)
    assert command.collection == collection
    mock_create.assert_called_once()


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.add_fragment_urls.Command.log_change")
@patch("geniza.corpus.models.GenizaManifestImporter")
def test_create_fragment(mock_importer, mock_log_change, fragment):
    collection = Collection.objects.create(library="Katz Center", lib_abbrev="CAJS")
    mock_importer.return_value.import_paths.return_value = [fragment.manifest]
    command = add_fragment_urls.Command()
    command.create = True
    command.collection = collection
    command.dryrun = False
    row = Dict(
        {
            "shelfmark": "CAJS RAR MS 82.313.1.3",
            "url": "https://example.com/items/abc",
            "iiif_url": "https://example.com/iiif/2/items/abc/manifest",
        }
    )
    command.add_fragment_urls(row)
    new_fragment = Fragment.objects.get(shelfmark=row.shelfmark)
    assert new_fragment.collection == collection
    assert new_fragment.url == row.url
    assert new_fragment.iiif_url == row.iiif_url
    assert new_fragment.manifest == fragment.manifest
    assert command.stats["created"] == 1
    assert not command.stats["not_found"]
    assert not command.stats["manifest_failed"]
    mock_log_change.assert_called_with(
        new_fragment, "created with URLs", action_flag=ADDITION
    )

    # dry run: report but don't create
    mock_log_change.reset_mock()
    command.dryrun = True
    command.add_fragment_urls(Dict({**row, "shelfmark": "CAJS RAR MS 82.313.1.4"}))
    assert not Fragment.objects.filter(shelfmark="CAJS RAR MS 82.313.1.4").exists()
    assert command.stats["created"] == 2
    assert not mock_log_change.call_count

    # shelfmark is a historical shelfmark of a renamed fragment: no duplicate
    command.dryrun = False
    new_fragment.shelfmark = "CAJS RAR MS 82.313.1.3a"
    new_fragment.save()
    command.add_fragment_urls(row)
    assert (
        Fragment.objects.filter(shelfmark__startswith="CAJS RAR MS 82.313.1.3").count()
        == 1
    )
    assert command.stats["created"] == 2
    # substring of a historical shelfmark is not a match
    command.add_fragment_urls(Dict({**row, "shelfmark": "CAJS RAR MS 82.313.1"}))
    assert Fragment.objects.filter(shelfmark="CAJS RAR MS 82.313.1").exists()

    # manifest import failure is reported
    mock_importer.return_value.import_paths.return_value = []
    command.add_fragment_urls(Dict({**row, "shelfmark": "CAJS RAR MS 85.126.1"}))
    assert command.stats["manifest_failed"] == 1


@pytest.mark.django_db
def test_log_change_addition(fragment):
    command = add_fragment_urls.Command()
    command.log_change(fragment, "created with URLs", action_flag=ADDITION)
    log_entry = LogEntry.objects.get(object_id=fragment.pk)
    assert log_entry.action_flag == ADDITION


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.add_fragment_urls.Command.log_change")
@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
def test_add_fragment_urls_old_shelfmark(mock_log_change):
    # fragment renamed after the csv was prepared; match by historical shelfmark
    fragment = Fragment.objects.create(shelfmark="UPenn RAR MS 82.313.1.2")
    fragment.shelfmark = "CAJS RAR MS 82.313.1.2"
    fragment.save()
    command = add_fragment_urls.Command()
    command.overwrite = False
    command.dryrun = False
    row = Dict(
        {"shelfmark": "UPenn RAR MS 82.313.1.2", "url": "https://example.com/items/abc"}
    )
    command.add_fragment_urls(row)
    fragment.refresh_from_db()
    assert fragment.url == row.url
    assert command.stats["url_added"] == 1
    assert not command.stats["not_found"]
    assert Fragment.objects.count() == 1


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.add_fragment_urls.IndexableSignalHandler")
def test_handle_skip_indexing(mock_signal_handler):
    command = add_fragment_urls.Command()
    mockfile = mock_open(read_data="shelfmark,url\na,b")
    with patch("geniza.corpus.management.commands.add_fragment_urls.open", mockfile):
        with patch.object(command, "add_fragment_urls"):
            command.handle(csv="foo.csv", skip_indexing=True)
    mock_signal_handler.disconnect.assert_called_once()


@pytest.mark.django_db
def test_add_fragment_urls_multiple_matches():
    # shelfmark is unique but case-sensitive; case-insensitive lookup matches both
    Fragment.objects.create(shelfmark="UPenn RAR MS A1")
    Fragment.objects.create(shelfmark="Upenn RAR MS A1")
    stdout = StringIO()
    command = add_fragment_urls.Command(stdout=stdout)
    command.add_fragment_urls(Dict({"shelfmark": "UPENN RAR MS A1", "url": "b"}))
    assert command.stats["not_found"] == 1
    assert "Found more than one fragment with shelfmark" in stdout.getvalue()

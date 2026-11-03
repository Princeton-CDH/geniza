from io import StringIO
from unittest.mock import mock_open, patch

import pytest
from django.core.management import call_command
from djiffy.models import Manifest

from geniza.corpus.management.commands import add_fragment_urls, import_manifests


def imported_urls(mock_importer):
    """urls passed to import_paths across all calls, since the
    command imports one url at a time"""
    return [
        url
        for args, kwargs in mock_importer.return_value.import_paths.call_args_list
        for url in args[0]
    ]


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.import_manifests.GenizaManifestImporter")
def test_handle(mock_importer, fragment_no_manifest, multifragment_no_manifest):
    # both fragment fixtures have iiif urls
    stdout = StringIO()
    command = import_manifests.Command(stdout=stdout)
    command.handle(update=False)
    assert mock_importer.return_value.import_paths.call_count == 2
    # both should be imported
    assert fragment_no_manifest.iiif_url in imported_urls(mock_importer)
    assert multifragment_no_manifest.iiif_url in imported_urls(mock_importer)

    # simulate one manifest already imported
    Manifest.objects.create(uri=fragment_no_manifest.iiif_url)
    mock_importer.reset_mock()
    command.handle(update=False)
    # should not import if already exists and update is false
    assert fragment_no_manifest.iiif_url not in imported_urls(mock_importer)
    assert multifragment_no_manifest.iiif_url in imported_urls(mock_importer)

    # when update is true, both should be imported
    mock_importer.reset_mock()
    command.handle(update=True)
    assert fragment_no_manifest.iiif_url in imported_urls(mock_importer)
    assert multifragment_no_manifest.iiif_url in imported_urls(mock_importer)

    # update with filter
    mock_importer.reset_mock()
    command.handle(update=True, filter="cudl")
    # should match iiif url for fragment but not multifragment
    assert imported_urls(mock_importer) == [fragment_no_manifest.iiif_url]


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.import_manifests.GenizaManifestImporter")
def test_handle_relink(mock_importer, fragment):
    # old url now returns a manifest with a different id (e.g. Penn server move);
    # fragment should be relinked from the outdated cached manifest to the new one
    old_manifest = fragment.manifest
    new_manifest = Manifest.objects.create(
        uri="https://example.com/iiif/new/manifest", short_id="new"
    )
    mock_importer.return_value.import_paths.return_value = [new_manifest]
    stdout = StringIO()
    import_manifests.Command(stdout=stdout).handle(update=True)
    fragment.refresh_from_db()
    assert fragment.manifest == new_manifest
    assert fragment.manifest != old_manifest
    assert "Relinked 1 fragments" in stdout.getvalue()

    # already linked; nothing to relink
    stdout = StringIO()
    import_manifests.Command(stdout=stdout).handle(update=True)
    assert "Relinked" not in stdout.getvalue()


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.import_manifests.GenizaManifestImporter")
def test_call_command(mock_importer):
    # test calling from command line; specified url should take precedence
    uri = "http://my.iiif.uri"
    call_command("import_manifests", uri)
    assert mock_importer.return_value.import_paths.call_count == 1
    args, kwargs = mock_importer.return_value.import_paths.call_args
    # both should be imported
    assert args[0] == [uri]

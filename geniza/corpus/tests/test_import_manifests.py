from io import StringIO
from unittest.mock import mock_open, patch

import pytest
from django.core.management import call_command
from djiffy.models import Manifest

from geniza.corpus.management.commands import add_fragment_urls, import_manifests


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.import_manifests.ManifestImporter")
def test_handle(mock_importer, fragment, multifragment):
    # both fragment fixtures have iiif urls
    stdout = StringIO()
    command = import_manifests.Command(stdout=stdout)
    command.handle(update=False)
    assert mock_importer.return_value.import_paths.call_count == 1
    args, kwargs = mock_importer.return_value.import_paths.call_args
    # both should be imported
    assert fragment.iiif_url in args[0]
    assert multifragment.iiif_url in args[0]

    # simulate one manifest already imported
    Manifest.objects.create(uri=fragment.iiif_url)
    command.handle(update=False)
    args, kwargs = mock_importer.return_value.import_paths.call_args
    # should not import if already exists and update is false
    assert fragment.iiif_url not in args[0]
    assert multifragment.iiif_url in args[0]

    # when update is true, both should be imported
    command.handle(update=True)
    args, kwargs = mock_importer.return_value.import_paths.call_args
    assert fragment.iiif_url in args[0]
    assert multifragment.iiif_url in args[0]


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.import_manifests.ManifestImporter")
def test_call_command(mock_importer):
    # test calling from command line; specified url should take precedence
    uri = "http://my.iiif.uri"
    call_command("import_manifests", uri)
    assert mock_importer.return_value.import_paths.call_count == 1
    args, kwargs = mock_importer.return_value.import_paths.call_args
    # both should be imported
    assert args[0] == [uri]

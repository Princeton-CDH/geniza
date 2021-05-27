from unittest.mock import patch, mock_open
from collections import namedtuple
from attrdict import AttrMap
import pytest

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


@pytest.mark.django_db
def test_the_import_iiif_url():
    # Ensure shelfmark not existing is properly handled.
    command = import_iiif_urls.Command()
    row = AttrMap({"shelfmark": "mm"})
    command.import_iiif_url(row)  # Test would fail if error were raised

    # Ensure that the iiif url is not overwritten unless overwrite arg is provided
    command = import_iiif_urls.Command(overwrite=None, dryrun=None)
    Fragment.objects.create(
        shelfmark="T-S NS 305.66",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = AttrMap(
        {
            "shelfmark": "T-S NS 305.66",
            "url": "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00600",
        }
    )
    command.import_iiif_url(row)
    fragment = Fragment.objects.get(shelfmark="T-S NS 305.66")
    assert fragment.iiif_url == "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490"

    command = import_iiif_urls.Command(overwrite=True, dryrun=None)
    Fragment.objects.create(
        shelfmark="T-S NS 305.75",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = AttrMap(
        {
            "shelfmark": "T-S NS 305.75",
            "url": "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00600",
        }
    )
    command.import_iiif_url(row)
    fragment = Fragment.objects.get(shelfmark="T-S NS 305.75")
    assert fragment.iiif_url == "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00600"

    # Ensure that changes aren't saved if dryrun argument is provided
    command = import_iiif_urls.Command(overwrite=None, dryrun=True)
    Fragment.objects.create(
        shelfmark="T-S NS 305.80",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490",
    )
    row = AttrMap(
        {
            "shelfmark": "T-S NS 305.80",
            "url": "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00600",
        }
    )
    command.import_iiif_url(row)
    fragment = Fragment.objects.get(shelfmark="T-S NS 305.80")
    assert fragment.iiif_url == "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-J-00490"

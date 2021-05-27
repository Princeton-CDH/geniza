from geniza.corpus.management.commands import import_iiif_urls
from unittest.mock import patch, mock_open


def test_get_iiif_csv():
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
        rows = list(command.get_iiif_csv())

    assert rows[0].shelfmark == "T-S NS 305.65"
    assert rows[1].url == "https://cudl.lib.cam.ac.uk/view/MS-TS-NS-00305-00069"

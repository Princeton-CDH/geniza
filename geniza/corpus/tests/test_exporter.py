import pytest

from geniza.corpus.admin import DocumentResource, FragmentResource


@pytest.mark.django_db
def test_doc_exporter_csv():
    dataset = DocumentResource().export()
    csv_string = dataset.csv
    print(len(csv_string), csv_string)

    first_line = csv_string.split("\n")[0].strip()
    assert "," in first_line
    assert " " not in first_line

    assert False

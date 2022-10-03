import pytest

from geniza.corpus.admin import DocumentResource


@pytest.mark.django_db
def test_doc_exporter_csv():
    dataset = DocumentResource().export()
    csv_string = dataset.csv

    first_line = csv_string.split("\n").strip()
    assert "," in first_line
    assert " " not in first_line

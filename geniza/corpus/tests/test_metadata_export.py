import csv

import pytest

from geniza.corpus.metadata_export import DocumentExporter


@pytest.mark.django_db
def test_doc_exporter_cli(document, join):
    # get artificial dataset
    exporter = DocumentExporter()

    # correct number of rows?

    ## ...in queryset?
    queryset = exporter.get_queryset()
    assert len(queryset) == 2

    ## ...in data?
    rows = list(exporter.iter_export_data_as_dicts())
    assert len(rows) == 2

    ## ...in csv output?
    testfn = "test_metadata_export.csv"
    exporter.write_export_data_csv(fn=testfn)
    with open(testfn) as f:
        csv_reader = csv.DictReader(f)
        assert len(list(csv_reader)) == 2  # 2 rows of data (as defined in conftest.py)

    iter = exporter.iter_export_data_as_dicts()
    row1 = next(iter)
    print(row1)
    assert row1["pgpid"] == document.id  # this should be first row

    # correct description in second row?
    row2 = next(iter)
    print(row2)
    assert row2.get("description") == join.description

import csv
import json
from io import StringIO

import pytest

from geniza.corpus.admin import DocumentResource, FragmentResource


@pytest.mark.django_db
def test_doc_exporter_csv(document, join):
    # get artificial dataset
    dataset = DocumentResource().export()

    # correct number of rows?
    ## ...in csv?
    csv_string = dataset.csv
    csv_reader = csv.DictReader(StringIO(csv_string))
    assert len(list(csv_reader)) == 2  # 2 rows of data (as defined in conftest.py)
    ## ...in json?
    json_data = json.loads(dataset.json)
    assert len(json_data) == 2  # 2 rows of data

    # correct id in first row?
    assert json_data[0]["id"] == 3951  # this should be first row

    # correct description in second row?
    assert json_data[1]["description"] == "testing description"

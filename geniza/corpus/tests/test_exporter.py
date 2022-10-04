import csv
import json
from io import StringIO

import pytest

from geniza.corpus.resource import DocumentResource


@pytest.mark.django_db
def test_doc_exporter_csv(document, join):
    # get artificial dataset
    dataset = DocumentResource().export()

    # correct number of rows?
    ## ...in csv?
    csv_string = dataset.csv
    print(csv_string)
    csv_reader = csv.DictReader(StringIO(csv_string))
    assert len(list(csv_reader)) == 2  # 2 rows of data (as defined in conftest.py)
    ## ...in json?
    json_data = json.loads(dataset.json)
    assert len(json_data) == 2  # 2 rows of data
    from pprint import pprint

    for d in json_data:
        pprint(d)
        print("\n")

    # correct id in first row?
    assert json_data[0].get("pgpid") == document.id  # this should be first row

    # correct description in second row?
    assert json_data[1].get("description") == join.description

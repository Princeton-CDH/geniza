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
    assert row1["pgpid"] == document.id  # this should be first row

    # correct description in second row?
    row2 = next(iter)
    assert row2.get("description") == join.description


# @pytest.mark.django_db
# def test_tabulate_queryset(self, document):
#     # Create all documents
#     cul = Collection.objects.create(library="Cambridge", abbrev="CUL")
#     frag = Fragment.objects.create(shelfmark="T-S 8J22.21", collection=cul)

#     contract = DocumentType.objects.create(name_en="Contract")
#     doc = Document.objects.create(
#         description="Business contracts with tables",
#         doctype=contract,
#         notes="Goitein cards",
#         needs_review="demerged",
#         status=Document.PUBLIC,
#     )
#     doc.fragments.add(frag)
#     doc.tags.add("table")

#     arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
#     french = LanguageScript.objects.create(language="French", script="Latin")

#     doc.languages.add(arabic)
#     doc.secondary_languages.add(french)

#     marina = Creator.objects.create(last_name_en="Rustow", first_name_en="Marina")
#     book = SourceType.objects.create(type="Book")
#     source = Source.objects.create(source_type=book)
#     source.authors.add(marina)
#     footnote = Footnote.objects.create(
#         doc_relation=["E"],
#         source=source,
#         content_type_id=ContentType.objects.get(
#             app_label="corpus", model="document"
#         ).id,
#         object_id=0,
#     )
#     doc.footnotes.add(footnote)

#     doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
#     doc_qs = Document.objects.all()

#     for doc, doc_data in zip(doc_qs, doc_admin.tabulate_queryset(doc_qs)):
#         # test some properties
#         assert doc.id in doc_data
#         assert doc.shelfmark in doc_data
#         assert doc.collection in doc_data

#         # test callables
#         assert doc.all_tags() in doc_data

#         # test new functions
#         assert f"https://example.com/documents/{doc.id}/" in doc_data
#         assert "Public" in doc_data
#         assert (
#             f"https://example.com/admin/corpus/document/{doc.id}/change/"
#             in doc_data
#         )
#         # initial input should be before last modified
#         # (document fixture has a log entry, so should have a first input)
#         input_date = doc_data[-6]
#         last_modified = doc_data[-5]
#         if input_date:
#             assert input_date < last_modified, (
#                 "expect input date (%s) to be earlier than last modified (%s) [PGPID %s]"
#                 % (input_date, last_modified, doc.id)
#             )

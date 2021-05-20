"""
To be run immediately after import_data. This script operates under the assumption 
    that a user has not taken advantage of the unique features offered by the 
    admin UI, but conforms to the expected format provided by the metadata spreadsheet.
"""


from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Collapse PGPIDs that share the same joins"""

    def get_documents_with_multiple_joins(self):
        pass
        # return [[doc1, doc2, doc3], [doc1, doc2]]

    def merge_documents(doc_list):
        primary_doc = min(doc_list, lambda d: d.pgpid)
        merge_docs = [doc for doc in doc_list if doc != primary_doc]

        # add old ids
        for doc in merge_docs:
            primary_doc.add_old_pgpid(doc.pgpid)

        # compress description
        # confirm doctype the same
        # compress unique tags
        # confirm languages all the same
        # confirm probable_languages are fine
        # language_note
        # notes
        # drop created
        # drop last_modified
        # collapse footnotes
        # ignoring log entries, status, created, last_modified, needs_review

        # primary_doc.save()
        # for doc in merge_docs:
        #   doc.delete()

    def handle(self, *args, **options):
        doc_groups = self.get_documents_with_multiple_joins()
        for doc_list in doc_groups:
            merge_documents(doc_list)

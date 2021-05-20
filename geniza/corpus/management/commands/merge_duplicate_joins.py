from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Collapse PGPIDs that share the same joins"""

    def get_documents_with_multiple_joins(self):
        pass
        # return [[doc1, doc2, doc3], [doc1, doc2]]

    def merge_documents(doc_list):
        pass

    def handle(self, *args, **options):
        doc_groups = self.get_documents_with_multiple_joins()
        for doc_list in doc_groups:
            merge_documents(doc_list)

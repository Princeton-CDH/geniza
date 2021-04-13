
from geniza.corpus.models import Document
from pytest_django.asserts import assertContains

class TestDocumentDetailView:
    def test_get_queryset(self, db, client):
        # Ensure page works normally when not suppressed
        doc = Document.objects.create()
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 200
        assertContains(response, "Shelfmark")

        # Test that when status isn't public, it is suppressed
        doc = Document.objects.create(status=Document.SUPPRESSED)
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 404

    def test_get_context_data(self, db, client):
        doc = Document.objects.create()

        # ensure view parses tags correctly
        doc.tags.add('10th century', 'Medical')
        response = client.get(doc.get_absolute_url())
        assert '#10th century' in response.context['tags']
        assert '#Medical' in response.context['tags']

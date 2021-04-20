from pytest_django.asserts import assertContains

class TestDocumentDetailTemplate:

    def test_shelfmark(self, client, document):
        """Document detail template should include shelfmark"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "<dd>CUL Add.2586</dd>", html=True)

    def test_doctype(self, client, document):
        """Document detail template should include document type"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "<dd>Legal</dd>", html=True)

    def test_first_input(self, client, document):
        """Document detail template should include document first input date"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "<dd>2021</dd>", html=True)

    def test_tags(self, client, document):
        """Document detail template should include all document tags"""
        response = client.get(document.get_absolute_url())
        assertContains(response, '<dd class="tag">bill of sale</dd>', html=True)
        assertContains(response, '<dd class="tag">real estate</dd>', html=True)

    def test_description(self, client, document):
        """Document detail template should include document description"""
        response = client.get(document.get_absolute_url())
        assertContains(response, f"<p>{document.description}</p>", html=True)

    def test_viewer(self, client, document):
        """Document detail template should include viewer for IIIF content"""
        pass

    def test_no_viewer(self, client, document):
        """Document with no IIIF shouldn't include viewer in template"""
        pass

    def test_multi_viewer(self, client, join):
        """Document with many IIIF urls should add all to viewer in template"""
        pass
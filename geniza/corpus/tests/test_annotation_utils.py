import pytest
from django.urls import Resolver404, reverse

from geniza.corpus.annotation_utils import document_id_from_manifest_uri


class TestIdFromManifestUri:
    def test_id_from_manifest_uri(self, document):
        # should resolve correct manifest URI to Document id
        resolved_doc_id = document_id_from_manifest_uri(
            reverse("corpus-uris:document-manifest", kwargs={"pk": document.pk})
        )
        assert isinstance(resolved_doc_id, int)
        assert resolved_doc_id == document.pk

        # should fail on resolvable non-manifest URI
        with pytest.raises(Resolver404):
            document_id_from_manifest_uri("http://bad.com/documents/3/")

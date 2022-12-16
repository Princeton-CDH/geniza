from urllib.parse import urlparse

from django.urls import Resolver404, resolve


def document_id_from_manifest_uri(uri):
    """
    Given a manifest URI (as used in transcription annotations), return the
    document id. Formerly a Document static method, extracted for use in a
    migration.
    """
    # will raise Resolver404 if url does not resolve
    resolve_match = resolve(urlparse(uri).path)
    # it could be a valid django url resolve but not be a manifest uri;
    if resolve_match.view_name != "corpus-uris:document-manifest":
        # is there a more appropriate exception to raise?
        raise Resolver404("Not a document manifest URL")
    return resolve_match.kwargs["pk"]

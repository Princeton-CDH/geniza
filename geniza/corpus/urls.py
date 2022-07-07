from django.urls import path

from geniza.corpus import views as corpus_views

app_name = "corpus"

urlpatterns = [
    path(
        "documents/", corpus_views.DocumentSearchView.as_view(), name="document-search"
    ),
    path(
        "documents/<int:pk>/",
        corpus_views.DocumentDetailView.as_view(),
        name="document",
    ),
    path(
        "documents/<int:pk>/scholarship/",
        corpus_views.DocumentScholarshipView.as_view(),
        name="document-scholarship",
    ),
    path(
        "documents/<int:pk>/related/",
        corpus_views.RelatedDocumentView.as_view(),
        name="related-documents",
    ),
    path(
        "documents/<int:pk>/transcription-editor",
        corpus_views.DocumentTranscribeView.as_view(),
        name="document-transcribe",
    ),
    path(
        "documents/<int:pk>/transcription/<int:transcription_pk>/",
        corpus_views.DocumentTranscriptionText.as_view(),
        name="document-transcription-text",
    ),
    path(
        "documents/<int:pk>/iiif/manifest/",
        corpus_views.DocumentManifestView.as_view(),
        name="document-manifest",
    ),
    path(
        "documents/<int:pk>/iiif/annotations/",
        corpus_views.DocumentAnnotationListView.as_view(),
        name="document-annotations",
    ),
    path("export/pgp-metadata-old/", corpus_views.pgp_metadata_for_old_site),
]

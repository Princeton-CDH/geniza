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
        "documents/<int:pk>/transcribe/",
        corpus_views.DocumentAddTranscriptionView.as_view(),
        name="document-add-transcription",
    ),
    path(
        "documents/<int:pk>/translate/",
        corpus_views.DocumentAddTranscriptionView.as_view(doc_relation="translation"),
        name="document-add-translation",
    ),
    path(
        "source-autocomplete/",
        corpus_views.SourceAutocompleteView.as_view(),
        name="source-autocomplete",
    ),
    path(
        "documents/<int:pk>/transcribe/<int:source_pk>/",
        corpus_views.DocumentTranscribeView.as_view(),
        name="document-transcribe",
    ),
    path(
        "documents/<int:pk>/translate/<int:source_pk>/",
        corpus_views.DocumentTranscribeView.as_view(doc_relation="translation"),
        name="document-translate",
    ),
    path(
        "documents/<int:pk>/transcription/<int:transcription_pk>/",
        corpus_views.DocumentTranscriptionText.as_view(),
        name="document-transcription-text",
    ),
    path("export/pgp-metadata-old/", corpus_views.pgp_metadata_for_old_site),
]

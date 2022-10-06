from django.urls import path

from geniza.corpus import views as corpus_views

app_name = "corpus"

# special set for IIIF urls that should not get i18n patterns
urlpatterns = [
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
]

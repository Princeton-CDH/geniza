from django.urls import path

from geniza.corpus.views import DocumentDetailView, pgp_metadata_for_old_site

app_name = "corpus"

urlpatterns = [
    path("documents/<int:pk>/", DocumentDetailView.as_view(), name="document"),
    path("export/pgp-metadata-old/", pgp_metadata_for_old_site),
]

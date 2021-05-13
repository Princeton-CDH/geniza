from django.urls import path

from geniza.corpus.views import DocumentDetailView, DocumentSearchView

app_name = "corpus"

urlpatterns = [
    path("documents/", DocumentSearchView.as_view(), name="document-search"),
    path("documents/<int:pk>/", DocumentDetailView.as_view(), name="document"),
]

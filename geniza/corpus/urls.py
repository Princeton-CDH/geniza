from django.urls import path

from geniza.corpus.views import DocumentDetailView, OldGenizaCsvSync

app_name = "corpus"

urlpatterns = [
    path("documents/<int:pk>/", DocumentDetailView.as_view(), name="document"),
    path("document-csv", OldGenizaCsvSync.render),
]

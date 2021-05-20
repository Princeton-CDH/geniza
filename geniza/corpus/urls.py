from django.urls import path

from geniza.corpus.views import DocumentDetailView, some_streaming_csv_view

app_name = "corpus"

urlpatterns = [
    path("documents/<int:pk>/", DocumentDetailView.as_view(), name="document"),
    path("document-csv", some_streaming_csv_view),
]

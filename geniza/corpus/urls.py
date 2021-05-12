from django.urls import path

from geniza.corpus.views import DocumentDetailView

app_name = "corpus"

urlpatterns = [
    path("documents/<int:pk>/", DocumentDetailView.as_view(), name="document"),
]

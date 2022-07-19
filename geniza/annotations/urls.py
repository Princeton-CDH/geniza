from django.urls import path

from geniza.annotations.views import AnnotationDetail, AnnotationList, AnnotationSearch

app_name = "annotations"

urlpatterns = [
    path("", AnnotationList.as_view(), name="list"),
    path("search/", AnnotationSearch.as_view(), name="search"),
    path("<uuid:pk>/", AnnotationDetail.as_view(), name="annotation"),
]

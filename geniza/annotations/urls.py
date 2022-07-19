from django.urls import path

from geniza.annotations.views import AnnotationDetail, AnnotationList

app_name = "annotations"

urlpatterns = [
    path("", AnnotationList.as_view(), name="list"),
    path("<uuid:pk>/", AnnotationDetail.as_view(), name="annotation"),
]

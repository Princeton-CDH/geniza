from django.urls import path

from geniza.entities import views as entities_views

app_name = "entities"

urlpatterns = [
    path(
        "people/<slug:slug>/",
        entities_views.PersonDetailView.as_view(),
        name="person",
    ),
    path(
        "person-autocomplete/",
        entities_views.PersonAutocompleteView.as_view(),
        name="person-autocomplete",
    ),
    path(
        "place-autocomplete/",
        entities_views.PlaceAutocompleteView.as_view(),
        name="place-autocomplete",
    ),
]

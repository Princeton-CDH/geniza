from django.urls import path

from geniza.entities import views as entities_views

app_name = "entities"

urlpatterns = [
    path("people/", entities_views.PersonListView.as_view(), name="person-list"),
    path(
        "people/<slug:slug>/",
        entities_views.PersonDetailView.as_view(),
        name="person",
    ),
    path(
        "people/<slug:slug>/documents/",
        entities_views.PersonDocumentsView.as_view(),
        name="person-documents",
    ),
    path(
        "people/<slug:slug>/people/",
        entities_views.PersonPeopleView.as_view(),
        name="person-people",
    ),
    path(
        "people/<slug:slug>/places/",
        entities_views.PersonPlacesView.as_view(),
        name="person-places",
    ),
    path(
        "person-autocomplete/",
        entities_views.PersonAutocompleteView.as_view(),
        name="person-autocomplete",
    ),
    path("places/", entities_views.PlaceListView.as_view(), name="place-list"),
    path(
        "places/<slug:slug>/",
        entities_views.PlaceDetailView.as_view(),
        name="place",
    ),
    path(
        "places/<slug:slug>/documents/",
        entities_views.PlaceDocumentsView.as_view(),
        name="place-documents",
    ),
    path(
        "places/<slug:slug>/people/",
        entities_views.PlacePeopleView.as_view(),
        name="place-people",
    ),
    path(
        "place-autocomplete/",
        entities_views.PlaceAutocompleteView.as_view(),
        name="place-autocomplete",
    ),
]

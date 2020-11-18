from django.urls import path

from . import views

app_name = "people"
urlpatterns = [
    path("", views.PersonListView.as_view(), name="list"),
    path("<int:pk>/", views.PersonDetailView.as_view(), name="detail"),
    path("professions/", views.ProfessionListView.as_view(), name="profession-list"),
]

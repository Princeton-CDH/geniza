from django.views.generic import DetailView, ListView

from .models import Person, Profession


class PersonListView(ListView):
    model = Person
    context_object_name = "people"


class PersonDetailView(DetailView):
    model = Person


class ProfessionListView(ListView):
    model = Profession
    context_object_name = "professions"

from django.views.generic import DetailView, ListView

from .models import Person


class PersonListView(ListView):
    model = Person
    context_object_name = "people"


class PersonDetailView(DetailView):
    model = Person

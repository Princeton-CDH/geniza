from django.views.generic import TemplateView

class HomepageView(TemplateView):
    template_name = "home.html"
from django.urls import path

from geniza.common import views as common_views

app_name = "common"

urlpatterns = [
    path(
        "language-switcher/", common_views.language_switcher, name="language-switcher"
    ),
]

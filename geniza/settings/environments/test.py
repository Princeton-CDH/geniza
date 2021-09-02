import os

from geniza.settings.components.base import DATABASES, INSTALLED_APPS

# These settings correspond to the service container settings in the
# .github/workflow .yml files.
DATABASES["default"].update(
    {
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "USER": os.getenv("DB_USER"),
        "NAME": os.getenv("DB_NAME"),
        "HOST": "127.0.0.1",
    }
)

# turn off debug so we see 404s when testing
DEBUG = False

# required for tests when DEBUG = False
ALLOWED_HOSTS = ["*"]

# enable django-dbml for generating dbdocs
INSTALLED_APPS.append("django_dbml")

# disable django-debug-toolbar so it doesn't appear in snapshot tests
INSTALLED_APPS.remove("debug_toolbar")
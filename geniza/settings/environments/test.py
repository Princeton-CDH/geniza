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

SOLR_CONNECTIONS["default"].update(
    {
        # set aggressive commitWithin for test
        "COMMITWITHIN": 750,
    }
)

# turn off debug so we see 404s when testing
DEBUG = False

# required for tests when DEBUG = False
ALLOWED_HOSTS = ["*"]

# enable django-dbml for generating dbdocs
INSTALLED_APPS.append("django_dbml")

# when running in CI, load fonts from production by overriding font base url
# (needed for Percy and Lighthouse)
if os.environ.get("CI"):
    FONT_URL_PREFIX = "https://geniza.cdh.princeton.edu/static/fonts/"

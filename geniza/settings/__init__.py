from os import environ

from split_settings.tools import include, optional

ENV = environ.get("DJANGO_ENV") or "development"

include(
    "components/base.py",
    "components/debug.py",
    # optionally load environment-specific configuration
    optional("environments/{0}.py".format(ENV)),
    # for now, local settings is required
    "local_settings.py",
)

from geniza.settings.components.base import INSTALLED_APPS

# if in debug mode, allow webpack dev server and django debug toolbar thru CSP
# from geniza.settings.components.base import CSP_SCRIPT_SRC

if DEBUG:
    CSP_SCRIPT_SRC += ["http://localhost:8000"]
    CSP_CONNECT_SRC += ["ws://localhost:3000"]

# enable fixture_magic for generating test fixtures
INSTALLED_APPS.append("fixture_magic")
# custom dump for fixture_magic
CUSTOM_DUMPS = {
    "document": {  # Initiate dump with: ./manage.py custom_dump document id1 id2 id3 ...
        "primary": "corpus.document",
        "dependents": [
            "tagged_items",
            "log_entries",
            "footnotes",
        ],
        "order": ("corpus.document", "footnotes.footnote"),
    },
}

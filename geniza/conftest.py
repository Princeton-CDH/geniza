"""Fixtures/utilities that should be globally available for testing."""
# FIXME not sure how else to share fixtures that depend on other fixtures
# between modules - if you import just the top-level fixture (e.g. "events"),
# it fails to find the fixture dependencies, and so on all the way down. For
# now this does what we want, although it pollutes the namespace somewhat
from geniza.annotations.conftest import *
from geniza.corpus.tests.conftest import *
from geniza.entities.conftest import *
from geniza.footnotes.conftest import *

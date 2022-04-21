Documents and Fragments
=======================

.. toctree::
   :maxdepth: 2

The :mod:`geniza.corpus` application is the heart of this project. The most imporant models are :class:`~geniza.corpus.models.Document` and :class:`~geniza.corpus.models.Fragment`, with a number of supporting models to track the source of the fragment, document type, languages and scripts used in a document, etc.


.. automodule:: geniza.corpus
    :members:

models
------

.. automodule:: geniza.corpus.models
    :members:

views
-----

.. automodule:: geniza.corpus.views
    :members:

template tags
-------------

.. automodule:: geniza.corpus.templatetags.corpus_extras
    :members:

manage commands
---------------

.. automodule:: geniza.corpus.management.commands.add_fragment_urls
    :members:

.. automodule:: geniza.corpus.management.commands.import_manifests
    :members:

.. automodule:: geniza.corpus.management.commands.merge_documents
    :members:

.. automodule:: geniza.corpus.management.commands.sync_transcriptions
    :members:

.. automodule:: geniza.corpus.management.commands.generate_fixtures
    :members:



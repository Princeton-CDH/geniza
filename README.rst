Princeton Geniza Project 
#########################



Python/Django web application for a new version of the `Princeton Geniza Project
<https://cdh.princeton.edu/projects/princeton-geniza-project/>`_.

Python 3.8 / Django 3.1 / Postgresql / Solr 8.6


.. image:: https://github.com/Princeton-CDH/geniza/workflows/unit%20tests/badge.svg
    :target: https://github.com/Princeton-CDH/geniza/actions?query=workflow%3Aunit&20tests
    :alt: Unit Test status

.. image:: https://codecov.io/gh/Princeton-CDH/geniza/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/Princeton-CDH/geniza
   :alt: Code coverage

.. image:: https://requires.io/github/Princeton-CDH/geniza/requirements.svg?branch=main
     :target: https://requires.io/github/Princeton-CDH/geniza/requirements/?branch=main
     :alt: Requirements Status

.. image:: https://github.com/Princeton-CDH/geniza/workflows/dbdocs/badge.svg
    :target: https://dbdocs.io/princetoncdh/geniza
    :alt: dbdocs build

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: code style: blacm

Development instructions
------------------------

Initial setup and installation:

- Recommended: create and activate a python 3.8 virtualenv

- Install required python dependencies::

    pip install -r requirements/dev.txt

- Copy sample local settings and configure for your environment::

	cp geniza/settings/local_settings.py.sample geniza/settings/local_settings.py

Remember to add a ``SECRET_KEY`` setting!

- Create a new database and update your database settings accordingly

- Run database migrations

    python manage.py migrate

- Compile microcopy and translated content to make it available for the application:

	cd geniza && django-admin compilemessages

- Copy Solr configset into your solr server configset directory. For a local install::

    cp -r solr_conf /path/to/solr/server/solr/configsets/geniza
    chown solr:solr -R /path/to/solr/server/solr/configsets/geniza

- Create Solr collection with the configured configset (use create_core with Solr standalone and create_collection with SolrCloud)::

    solr create_core -c geniza -n geniza
- Index content in Solr::

    python manage.py index


Internationalization & Translation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This application has internationalization and translation enabled.

- If you create any new translatable content, you should run `makemessages <https://docs.djangoproject.com/en/3.1/ref/django-admin/#makemessages>`_ to create or update message files.

	cd geniza && django-admin makemessages

Unit Tests
----------

Python unit tests are written with `py.test <http://doc.pytest.org/>`_
and should be run with `pytest`.


Setup Black
-----------

If you plan to contribute to this repository (i.e., you're a member of the CDH dev team), please run the following command:

    pre-commit install

This will add a simple pre-commit hook that will automatically style your python code. Read more about `black <https://github.com/psf/black>`_.

Black styling was instituted after development had begun on this project. Consequently, ``git blame`` may not reflect the true author of a given line. In order to see a more accurate ``git blame`` execute the following command:

    git blame <FILE> --ignore-revs-file .git-blame-ignore-revs

Or configure your git to always ignore the black revision commit:

    git config blame.ignoreRevsFile .git-blame-ignore-revs


License
-------
This project is licensed under the `Apache 2.0 License <https://github.com/Princeton-CDH/mep-django/blob/main/LICENSE>`_.

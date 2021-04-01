# Princeton Geniza Project Research Partnership


Python/Django web application for a new version of the `Princeton Geniza Project
<https://cdh.princeton.edu/projects/princeton-geniza-project/>`_.

Python 3.8 / Django 3.1 / Postgresql


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


Internationalization & Translation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This application has internationalization and translation enabled.

- If you create any new translatable content, you should run `makemessages <https://docs.djangoproject.com/en/3.1/ref/django-admin/#makemessages>`_ to create or update message files.

	cd geniza && django-admin makemessages

Unit Tests
----------

Python unit tests are written with `py.test <http://doc.pytest.org/>`_
and should be run with `pytest`.

License
-------
This project is licensed under the `Apache 2.0 License <https://github.com/Princeton-CDH/mep-django/blob/main/LICENSE>`_.

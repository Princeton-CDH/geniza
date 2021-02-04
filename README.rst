# Princeton Geniza Project Research Partnership


Python/Django web application for a new version of the `Princeton Geniza Project
<https://cdh.princeton.edu/projects/princeton-geniza-project/>`_.

Python 3.8 / Django 3.1 / Postgresql


Development instructions
------------------------

Initial setup and installation:

- Recommended: create and activate a python 3.8 virtualenv

- Install required python dependencies::

    pip install -r requirements/dev.txt

- Copy sample local settings and configure for your environment::

    cp geniza/local_settings.py.sample geniza/local_settings.py

Remember to add a ``SECRET_KEY`` setting!

- Create an empty database and configure your local settings accordingly

- Run datbase migrations

    python manage.py migrate


Unit Tests
----------

Python unit tests are written with `py.test <http://doc.pytest.org/>`_
and should be run with `pytest`.

License
-------
This project is licensed under the `Apache 2.0 License <https://github.com/Princeton-CDH/mep-django/blob/main/LICENSE>`_.

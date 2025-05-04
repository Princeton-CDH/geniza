Developer Instructions
======================

Setup and installation
-----------------------

Initial setup and installation:

- Recommended: create and activate a python 3.8 virtualenv

- Install required python dependencies::

    pip install -e '.[dev]'

- Recommended: use `Volta <https://volta.sh/>`_ for Node version management

- Install required javascript dependencies::

    npm install

- Copy sample local settings and configure for your environment::

    cp geniza/settings/local_settings.py.sample geniza/settings/local_settings.py

Remember to add a ``SECRET_KEY`` setting!

- Create a new database and update your database settings accordingly

- Run database migrations::

    python manage.py migrate

- Compile microcopy and translated content to make it available for the application::

    cd geniza && django-admin compilemessages

- Copy Solr configset into your solr server configset directory. For a local install:

    cp -r solr_conf /path/to/solr/server/solr/configsets/geniza
    chown solr:solr -R /path/to/solr/server/solr/configsets/geniza

- Create Solr collection with the configured configset (use `create_core` with Solr standalone and `create_collection` with SolrCloud)::

    curl "http://localhost:8983/solr/admin/cores?action=CREATE&name=geniza&configSet=geniza"

.. note::
    The command line version of core creation looks like ``solr create -c geniza -n geniza``, but in
    current versions of Solr it creates a new core with a *copy* of the configset instead of a *reference*.

- Index content in Solr::

    python manage.py index


Install pre-commmit hooks
~~~~~~~~~~~~~~~~~~~~~~~~~

We use `pre-commit <https://pre-commit.com/>`_ to install and manage commit hooks to ensure that code is consistently formatted. To install, run::

    pre-commit install

Current hooks include Black for python code formatting, isort for standardized python imports, djhtml for consistent indentation in django templates, and prettier for javascript, css, and other supported file types.

Standardized code styles were instituted after development had begun on this project. Consequently, ``git blame`` may not reflect the true author of a given line. In order to see a more accurate ``git blame`` execute the following command::

    git blame <FILE> --ignore-revs-file .git-blame-ignore-revs

Or configure your git to always ignore the black revision commit::

    git config blame.ignoreRevsFile .git-blame-ignore-revs

Fonts
~~~~~

Fonts are stored in ``sitemedia/fonts/``. Since this project uses paid licensed fonts, this directory is ignored by git and not checked into version control.

Instead, licnsed fonts are stored in an AES-256 encrypted ``.zip`` archive, and this file is checked into the repo. The encryption key is stored as a GitHub Secret, used by Percy (visual regression testing service) and Lighthouse (accessibility testing serivce) to decrypt and use the fonts in GitHub Actions.

To install fonts locally:

- Download ``.woff`` and ``.woff2`` files from the shared Google Drive folder "Geniza – woff files only".

- Create the ``fonts`` subdirectory::

    cd sitemedia && mkdir fonts

- Move or copy all the ``.woff`` and ``.woff2`` files into that subdirectory.

Alternatively, if you have access to a project maintainer who has the decryption passphrase, you can decrypt and unzip the file with GPG (via the ``gpg`` package on Unix or `GPGTools <https://gpgtools.org/>`_ on MacOS) and ``unzip`` or your preferred unzipper::

    gpg --quiet --batch --yes --decrypt --passphrase="PASSPHRASE" --output fonts.zip fonts.zip.gpg
    unzip -q -o sitemedia/fonts.zip -d sitemedia

Where ``PASSPHRASE`` is the correct passphrase.

If you need to add fonts to the bundle, you will need access to the original font files, either by using the above commands to decrypt and unizp the original encrypted file (recommended), or by following the Google Drive steps. Add your new fonts to the `fonts` directory, and then zip and re-encrypt with the following commands::

    cd sitemedia
    rm -rf fonts.zip.gpg    # Remove the original encrypted file
    zip -r fonts.zip fonts  # Compress the directory into a new zip file
    gpg --symmetric --cipher-algo AES256 fonts.zip # Generate a new encrypted file
    rm -rf fonts.zip        # Remove the unencrypted zip

When prompted after entering the ``gpg`` command, you must use the same passphrase that was previously used to encrypt the file, or store the new passphrase in GitHub Secrets in a variable called ``GPG_PASSPHRASE``.

Static Files
~~~~~~~~~~~~

Static files are stored in ``sitemedia/`` and bundled by Webpack. The ``webpack-bundle-tracker`` plugin generates a JSON manifest file listing the name and location of bundled files. This file, ``webpack-stats.json``, is read by Django using ``django-webpack-loader`` so that the relevant files can be included in the template's ``<head>``.

Bundled files will be output into the ``sitemedia/bundles`` directory and picked up by Django's ``collectstatic`` command. To recompile bundles after making changes::

    npm run build

When actively developing stylesheets and scripts, you can instead run a development Webpack server, which will recompile the bundle and refresh your browser when changes are saved::

    npm start

Note that switching to the development Webpack server requires restarting your Django server, if one is running, in order to pick up the changes in ``webpack-stats.json``.

JavaScript sources are transpiled using Babel so that modern features are supported. Source files that will be transpiled are stored using the ``.esm.js`` (EcmaScript module) file extension to indicate that they should not be directly included in templates. These files will not be collected as part of Django's ``collectstatic`` command.

SCSS sources are compiled using Autoprefixer so that vendor prefixes for browser support of newer CSS features will be added automatically. Source files to be transpiled are stored with the ``.scss`` file extension for interoperability with CSS. These files will not be collected as part of Django's ``collectstatic`` command.

See the ``.browserslistrc`` file for more information about browser versions officially supported by this application. This file controls the automatic insertion of vendor prefixes for CSS and polyfills for JavaScript so that bundled styles and scripts will be supported on all target browsers.

Internationalization & Translation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This application has internationalization and translation enabled.

- If you create any new translatable content, you should run `makemessages <https://docs.djangoproject.com/en/3.1/ref/django-admin/#makemessages>`_ to create or update message files. We use a customized version of this command, available in ``/geniza/common/management/commands/makemessages.py``.

	django-admin makemessages --all

- Before running the app, you should run `compilemessages <https://docs.djangoproject.com/en/3.1/ref/django-admin/#compilemessages>`_ to generate compiled translations.

    django-admin compilemessages

Unit Tests
----------

Python unit tests are written with `py.test <http://doc.pytest.org/>`_
and should be run with ``pytest``.

End-to-end Tests
----------------

Performance, accessibility, SEO and more are audited via `Lighthouse <https://developers.google.com/web/tools/lighthouse>`_. The tool runs in a GitHub actions workflow (``lighthouse.yml``).

Lighthouse runs several checks by visiting a list of URLs and averaging the results. If new pages are adding to the site, a corresponding URL should be added to the configuration file ``lighthouserc.js``.

If the Lighthouse build is generating errors that need to be temporarily or permanently ignored, the corresponding error code can be set to "off" or "warn" in ``lighthouserc.js``.

Visual Tests
------------

Visual regressions are monitored with `Percy <https://percy.io/>`_. Percy takes screenshots of the web application with different browsers and compares them to a set of base screenshots to find changes.

In this repository, a GitHub Action is configured to take a set of Percy screenshots when one of the following conditions is met:

#. A commit has been pushed to a pull request against the ``develop`` branch, and the phrase ``[run percy]`` is present in the commit message.
#. A commit has been pushed to the ``develop`` branch, and the phrase ``[skip percy]`` is NOT present in the commit message.

Otherwise, the action will be skipped and Percy will not take a set of screenshots to check for visual regressions.